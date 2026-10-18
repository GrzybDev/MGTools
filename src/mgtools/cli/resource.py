"""Commands for the resource files of the MSX games."""

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from mgtools.cli.commands import (
    FormatOption,
    add_import_command,
    exporting,
    input_argument,
    output_argument,
)
from mgtools.cli.console import console, reports_errors
from mgtools.msx.font_editable import read_charmap
from mgtools.msx.game import Game
from mgtools.msx.resource import describe_resource, export_resource, import_resource
from mgtools.translation import TranslationFormat

app = typer.Typer(
    help="Resource files of the MSX games (Resource/*.bin, "
    "*/stage/mg?/cache/**/*.raw): images, palettes, texts, fonts and game data.",
    no_args_is_help=True,
)

_TITLES = {Game.MG1: "Metal Gear", Game.MG2: "Metal Gear 2: Solid Snake"}


@app.command()
@reports_errors
def info(file: Annotated[Path, input_argument("The resource file")]) -> None:
    """Show which game a resource file belongs to and what its sections hold."""
    game, sections = describe_resource(file.read_bytes())
    console.print(f"{_TITLES[game]}, {len(sections)} sections")
    table = Table("Section", "Holds", "Leaves", "Bytes")
    for index, section in enumerate(sections):
        table.add_row(str(index), section.kind, str(section.leaves), str(section.size))
    console.print(table)


@app.command(name="export")
@reports_errors
def export_command(
    file: Annotated[Path, input_argument("The resource file")],
    output: Annotated[
        Path | None, output_argument("The new or empty folder to write", folder=True)
    ] = None,
    fmt: FormatOption = TranslationFormat.XLIFF2,
    charmap: Annotated[
        Path | None,
        typer.Option(
            help="The font.json of an earlier export, whose charmap names the "
            "characters of the codes (default: those the game shipped with)",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
) -> None:
    """Export a resource file as PNG images, JSON, its texts for translation tools and its undecoded data as .bin files."""  # noqa: E501 - Typer keeps a docstring's line breaks in its list of commands
    names = read_charmap(charmap) if charmap else None
    with exporting(file, output, "") as target:
        export_resource(file.read_bytes(), target, fmt, names)


add_import_command(
    app,
    suffix=".raw",
    editable_suffix="",
    build=import_resource,
    help_text="Import a resource file from a folder export wrote.",
)
