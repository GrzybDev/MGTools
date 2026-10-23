"""Commands for the GCX scripts."""

from itertools import islice
from pathlib import Path
from typing import Annotated

import typer

from mgtools.cli.commands import (
    FormatOption,
    add_import_command,
    exporting,
    input_argument,
    output_argument,
)
from mgtools.cli.console import reports_errors, warn
from mgtools.mc.gcx.dictionary import read_dictionary
from mgtools.mc.gcx.editable import export_script, import_script
from mgtools.mc.gcx.script import decode_script, encode_script
from mgtools.translation import TranslationFormat

app = typer.Typer(
    help="GCX scripts (*.gcx): the code and texts of the stages.", no_args_is_help=True
)
# Enough lines to tell a header, a comment column or a typo from one another, without
# filling the console for a dictionary of mostly unusable lines.
_SHOWN_SKIPPED_LINES = 3


@app.command(name="export")
@reports_errors
def export_command(
    file: Annotated[Path, input_argument("The .gcx file")],
    output: Annotated[
        Path | None, output_argument("The new or empty folder to write", folder=True)
    ] = None,
    fmt: FormatOption = TranslationFormat.XLIFF2,
    source_language: Annotated[
        str,
        typer.Option(
            "--source-language",
            "-l",
            help="The language of the texts, as a BCP 47 tag (XLIFF only)",
        ),
    ] = "en",
    dictionary: Annotated[
        Path | None,
        typer.Option(
            help="A file of strcodes in hex and their names, one a line, whose names the "
            "listing writes instead of the strcodes (default: the built-in names only)",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
) -> None:
    """Export a script as its listing, its texts for translation tools and its glyphs."""
    names = _names(dictionary) if dictionary else None
    with exporting(file, output, "") as target:
        script = decode_script(file.read_bytes())
        export_script(
            script,
            target,
            fmt,
            original=file.name,
            source_language=source_language,
            names=names,
        )


def _names(path: Path) -> dict[int, str]:
    """Return the names of a dictionary, warning about the lines it skips."""
    dictionary = read_dictionary(path)
    if count := len(dictionary.skipped):
        shown = islice(dictionary.skipped.items(), _SHOWN_SKIPPED_LINES)
        lines = [f"Line {number}: {reason}" for number, reason in shown]
        if count > len(lines):
            lines.append(f"and {count - len(lines)} more")
        noun = "line" if count == 1 else "lines"
        details = "".join(f"\n  {line}" for line in lines)
        warn(f"{path}: skipped {count} {noun} that a listing cannot use:{details}")
    return dictionary.names


add_import_command(
    app,
    suffix=".gcx",
    editable_suffix="",
    build=lambda source: encode_script(import_script(source)),
    help_text="Import a script from a folder export wrote.",
)
