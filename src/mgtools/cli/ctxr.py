"""Commands for the textures, which read one file, a folder or a wildcard pattern."""

import re
from collections.abc import Callable
from itertools import takewhile
from pathlib import Path
from typing import Annotated, Any

import typer

from mgtools.cli.commands import importing, refuse_existing
from mgtools.cli.console import done, reports_errors, working
from mgtools.errors import located
from mgtools.fileio import write_atomically
from mgtools.mc.ctxr import (
    decode_texture,
    encode_texture,
    export_texture,
    import_texture,
)

app = typer.Typer(help="Textures (*.ctxr): images and their mipmaps.", no_args_is_help=True)

_SETTINGS = ".json"
_WILDCARD = re.compile(r"[*?[]")


def _output_argument(suffix: str) -> Any:
    """Return the argument of the file, or the folder for several, a command writes.

    Args:
        suffix: The suffix of the files the command writes.
    """
    return typer.Argument(
        help=f"The {suffix} file to write, or the folder to write to for a folder or "
        "pattern (default: next to each input, named after it)",
    )


@app.command(name="export")
@reports_errors
def export_command(
    source: Annotated[
        Path,
        typer.Argument(
            help="The .ctxr file, a folder of them or a wildcard pattern such as textures/*.ctxr"
        ),
    ],
    output: Annotated[Path | None, _output_argument(".png")] = None,
) -> None:
    """Export a texture's full-size level as a PNG, with the alpha as stored, and its settings as JSON next to it."""  # noqa: E501 - Typer keeps a docstring's line breaks in its list of commands
    files, base = _inputs(source, ".ctxr file", _is_texture)
    targets = _outputs(files, base, output, ".png")
    for target in targets:
        refuse_existing(target)
        refuse_existing(target.with_suffix(_SETTINGS))
    textures = []
    for file in files:
        with working(f"Reading {file}"), located(file):
            textures.append(decode_texture(file.read_bytes()))
    for file, target, texture in zip(files, targets, textures, strict=True):
        with working(f"Exporting {file}"):
            export_texture(texture, target)
        done(f"Exported {file} to {target}")


@app.command(name="import")
@reports_errors
def import_command(
    source: Annotated[
        Path,
        typer.Argument(
            help="The .png file export wrote, a folder of them or a wildcard pattern such as "
            "textures/*.png"
        ),
    ],
    output: Annotated[Path | None, _output_argument(".ctxr")] = None,
) -> None:
    """Import a texture from a PNG and the JSON next to it, remaking the mipmaps as the game's converter does."""  # noqa: E501 - Typer keeps a docstring's line breaks in its list of commands
    files, base = _inputs(source, f".png file with its {_SETTINGS} settings beside it", _is_export)
    targets = _outputs(files, base, output, ".ctxr")
    built = []
    for file in files:
        with working(f"Reading {file}"):
            built.append(encode_texture(import_texture(file)))
    for file, target, data in zip(files, targets, built, strict=True):
        with importing(file, target, ".ctxr"):
            write_atomically(target, data)


def _inputs(
    source: Path, kind: str, selected: Callable[[Path], bool]
) -> tuple[list[Path], Path | None]:
    """Return the files source names, and the folder whose layout an output folder keeps.

    A path that exists is never read as a pattern, and a file a pattern names by several
    paths is returned once. The folder is None for a single file, whose output is a file.

    Args:
        source: A file, a folder whose selected files are read, or a wildcard pattern.
        kind: The kind of the files read, as messages name it.
        selected: Tell whether a file is of that kind.
    """
    if source.is_dir():
        files = sorted(filter(selected, source.iterdir()))
        if not files:
            raise _invalid("source", f"{source} holds no {kind}")
        return files, source
    if source.exists():
        return [source], None
    base = Path(*takewhile(lambda part: not _WILDCARD.search(part), source.parts))
    if base == source:
        raise _invalid("source", f"{source} does not exist")
    # PowerShell and cmd pass wildcards on unexpanded, so the command expands them itself.
    found: dict[Path, Path] = {}
    for file in sorted(base.glob(str(source.relative_to(base)))):
        found.setdefault(file.resolve(), file)
    files = list(found.values())
    if not files:
        raise _invalid("source", f"{source} matches no file")
    if other := next((file for file in files if not selected(file)), None):
        raise _invalid("source", f"{source} matches {other}, which is not a {kind}")
    return files, base


def _outputs(files: list[Path], base: Path | None, output: Path | None, suffix: str) -> list[Path]:
    """Return where each file is written: at or under output, else next to the file.

    Refuses an output of the wrong kind, and two files written to the same place.

    Args:
        files: The files a command reads.
        base: The folder whose layout an output folder keeps, None for a single file.
        output: The file to write for a single file, else the folder to write to, or None.
        suffix: The suffix of the files written.
    """
    if base is None:
        if output and output.is_dir():
            raise _invalid("output", f"{output} is a folder, not a {suffix} file")
        if output and output.suffix == files[0].suffix:
            msg = (
                f"{output} is a {output.suffix} file like the input, not a {suffix} file; POSIX "
                "shells turn an unquoted pattern into the files it matches, so put it in quotes"
            )
            raise _invalid("output", msg)
        return [output or files[0].with_suffix(suffix)]
    if output and output.is_file():
        raise _invalid("output", f"{output} is a file, not a folder")
    targets = [
        (output / file.relative_to(base) if output else file).with_suffix(suffix) for file in files
    ]
    written: dict[Path, Path] = {}
    for file, target in zip(files, targets, strict=True):
        if (other := written.setdefault(target.resolve(), file)) is not file:
            raise _invalid("output", f"{other} and {file} would both be written to {target}")
    return targets


def _invalid(argument: str, message: str) -> typer.BadParameter:
    """Return the error of an argument that names nothing the command can read or write.

    Args:
        argument: The argument's name.
        message: What the argument names, and why the command refuses it.
    """
    return typer.BadParameter(message, param_hint=f"'{argument}'")


def _is_texture(path: Path) -> bool:
    return path.suffix == ".ctxr" and path.is_file()


def _is_export(path: Path) -> bool:
    return path.suffix == ".png" and path.is_file() and path.with_suffix(_SETTINGS).is_file()
