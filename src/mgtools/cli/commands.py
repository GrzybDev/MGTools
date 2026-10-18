"""The arguments, options and export and import commands the command groups share."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer

from mgtools.cli.console import done, reports_errors, working
from mgtools.fileio import original_to_keep, write_atomically
from mgtools.translation import TranslationFormat

FormatOption = Annotated[
    TranslationFormat,
    typer.Option("--format", "-f", help="The format of the texts to translate"),
]


def input_argument(description: str, *, folder: bool = False) -> Any:
    """Return the argument of the file or folder a command reads.

    Args:
        description: The argument's help.
        folder: Whether the argument names a folder rather than a file.
    """
    return typer.Argument(help=description, exists=True, file_okay=not folder, dir_okay=folder)


def output_argument(description: str, *, folder: bool = False) -> Any:
    """Return the argument of the file or folder a command writes.

    Args:
        description: The argument's help, before the note on its default.
        folder: Whether the argument names a folder rather than a file.
    """
    return typer.Argument(
        help=f"{description} (default: next to the input, named after it)",
        file_okay=not folder,
        dir_okay=folder,
    )


def output_path(source: Path, suffix: str) -> Path:
    """Return where a command writes by default: next to source, named after it.

    Args:
        source: The file or folder the command reads.
        suffix: The suffix of the output, empty for a folder.
    """
    if source.is_dir():
        source = source.resolve()  # "." has no name to call the output after
        return source.with_name(source.name + suffix)
    return source.with_suffix(suffix)


def refuse_existing(path: Path) -> None:
    """Refuse to export to an existing file or a non-empty folder, which may hold edits.

    Args:
        path: The file or folder an export writes.
    """
    if path.is_dir() and any(path.iterdir()):
        msg = f"{path} is not empty; it is kept and nothing was written"
        raise FileExistsError(msg)
    if path.is_file():
        msg = f"{path} already exists; it is kept and nothing was written"
        raise FileExistsError(msg)


@contextmanager
def exporting(file: Path, output: Path | None, suffix: str) -> Iterator[Path]:
    """Report the export of a file while the block writes it, yielding where it goes.

    Args:
        file: The game file to export.
        output: The file or folder to write, or None for the one output_path names.
        suffix: The suffix of that default, empty for a folder.
    """
    output = output or output_path(file, suffix)
    refuse_existing(output)
    with working(f"Exporting {file}"):
        yield output
    done(f"Exported {file} to {output}")


@contextmanager
def importing(source: Path, output: Path | None, suffix: str) -> Iterator[Path]:
    """Report the import of an export while the block builds it, yielding where it goes.

    The block's write keeps the file it replaces as original_to_keep says.

    Args:
        source: The file or folder an export wrote.
        output: The game file to write, or None for the one output_path names.
        suffix: The suffix of that default.
    """
    output = output or output_path(source, suffix)
    original = original_to_keep(output)
    with working(f"Importing {source}"):
        yield output
    done(f"Imported {source} to {output}")
    if original:
        done(f"Kept the original as {original}")


def add_import_command(
    app: typer.Typer,
    *,
    suffix: str,
    editable_suffix: str,
    build: Callable[[Path], bytes],
    help_text: str,
) -> None:
    """Add the command that builds a file of suffix from its editable form.

    Args:
        app: The command group to add the command to.
        suffix: The suffix of the files the command builds.
        editable_suffix: The suffix of the editable file, empty for a folder.
        build: Return the contents of the file built from an editable file or folder.
        help_text: The command's help.
    """
    folder = not editable_suffix

    @app.command(name="import", help=help_text)
    @reports_errors
    def import_command(
        source: Annotated[
            Path, input_argument(f"The {_editable(editable_suffix)} export wrote", folder=folder)
        ],
        output: Annotated[Path | None, output_argument(f"The {suffix} file to write")] = None,
    ) -> None:
        with importing(source, output, suffix) as target:
            write_atomically(target, build(source))


def _editable(editable_suffix: str) -> str:
    """Return the name of the editable form in an argument's help: a file or a folder.

    Args:
        editable_suffix: The suffix of the editable file, empty for a folder.
    """
    return f"{editable_suffix} file" if editable_suffix else "folder"
