"""Commands for the string tables."""

from pathlib import Path
from typing import Annotated

import typer

from mgtools.cli.commands import (
    FormatOption,
    exporting,
    importing,
    input_argument,
    output_argument,
)
from mgtools.cli.console import reports_errors
from mgtools.fileio import write_atomically
from mgtools.mc.stov import decode_stov, encode_stov, export_stov, import_stov
from mgtools.translation import TranslationFormat

app = typer.Typer(
    help="String tables (stovc.bin, stovk.bin): the engine's texts in several languages.",
    no_args_is_help=True,
)


@app.command(name="export")
@reports_errors
def export_command(
    file: Annotated[Path, input_argument("The string table")],
    output: Annotated[Path | None, output_argument("The translation document to write")] = None,
    fmt: FormatOption = TranslationFormat.XLIFF2,
) -> None:
    """Export a string table for translation tools, a unit per string named by its hex id and language, such as 000e66b2.en."""  # noqa: E501 - Typer keeps a docstring's line breaks in its list of commands
    with exporting(file, output, fmt.suffix) as target:
        export_stov(decode_stov(file.read_bytes(), file.name), target, fmt, file.name)


@app.command(name="import")
@reports_errors
def import_command(
    source: Annotated[Path, input_argument("The translation document")],
    output: Annotated[Path | None, output_argument("The .bin file to write")] = None,
) -> None:
    """Import a string table from a translation document, keeping the text of untranslated strings. The table's name up to its first dot is its key, so keep stovc or stovk."""  # noqa: E501 - Typer keeps a docstring's line breaks in its list of commands
    with importing(source, output, ".bin") as target:
        write_atomically(target, encode_stov(import_stov(source), target.name))
