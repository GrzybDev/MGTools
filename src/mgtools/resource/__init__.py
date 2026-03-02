from pathlib import Path
from typing import Annotated

import typer

from mgtools.dataclasses.locale_format import LocaleFormat
from mgtools.enumerators.game import Game
from mgtools.mg1.constants import RESOURCE_SECTION_COUNT as MG1_SECTION_COUNT
from mgtools.mg2.constants import RESOURCE_SECTION_COUNT as MG2_SECTION_COUNT
from mgtools.resource.file import Resource

app = typer.Typer(
    help="Tools for working with resource files (English.bin, English.raw etc.)"
)


@app.command(
    "unpack",
    help="Unpack resources from specified resource file. (English.bin, English.raw etc.)",
)
def resource_unpack(
    input_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_dir: Annotated[
        Path | None, typer.Argument(file_okay=False, writable=True)
    ] = None,
    separate_chars: Annotated[
        bool,
        typer.Option(help="Export font glyphs as separate images instead of an atlas."),
    ] = False,
    locale_format: Annotated[
        LocaleFormat,
        typer.Option(
            help="Format to export locale text blocks in. XLIFF is more widely supported, but XLIFF2 is more compact and easier to work with."
        ),
    ] = LocaleFormat.XLF,
):
    if output_dir is None:
        output_dir = input_file.parent / input_file.stem

    resource = Resource.from_file(input_file)
    resource.save_metadata(output_dir)

    for index in range(resource.section_count):
        resource.unpack(
            output_dir,
            index,
            separate_chars=separate_chars,
            locale_format=locale_format,
        )


@app.command("pack", help="Pack new resource file from specified folder.")
def resource_pack(
    input_dir: Annotated[Path, typer.Argument(dir_okay=True, readable=True)],
    output_file: Annotated[
        Path | None, typer.Argument(file_okay=True, writable=True)
    ] = None,
):
    game = Resource.detect_game(input_dir)

    if game == Game.MG1:
        section_count = MG1_SECTION_COUNT
    else:
        section_count = MG2_SECTION_COUNT

    if output_file is None:
        output_file = input_dir / f"{input_dir.name}.bin"

    resource = Resource(game=game)

    for index in range(section_count):
        resource.add_from_folder(input_dir, index)

    resource.save(output_file)
