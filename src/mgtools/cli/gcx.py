"""Commands for the GCX scripts."""

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
from mgtools.cli.console import reports_errors
from mgtools.mc.gcx.editable import export_script, import_script
from mgtools.mc.gcx.script import decode_script, encode_script
from mgtools.translation import TranslationFormat

app = typer.Typer(
    help="GCX scripts (*.gcx): the code and texts of the stages.", no_args_is_help=True
)


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
) -> None:
    """Export a script as its listing, its texts for translation tools and its glyphs."""
    with exporting(file, output, "") as target:
        script = decode_script(file.read_bytes())
        export_script(script, target, fmt, original=file.name, source_language=source_language)


add_import_command(
    app,
    suffix=".gcx",
    editable_suffix="",
    build=lambda source: encode_script(import_script(source)),
    help_text="Import a script from a folder export wrote.",
)
