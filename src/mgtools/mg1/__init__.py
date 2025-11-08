from pathlib import Path
from typing import Annotated

import typer

from mgtools.enumerators.game import Game
from mgtools.enumerators.platform import Platform
from mgtools.mg1.constants import RESOURCE_FILES_COUNT
from mgtools.resource import Resource

app = typer.Typer(help="Tools for modding PC ports of Metal Gear")


@app.command(
    help="Export resources from specified resource file. (English.bin, English.raw etc.)"
)
def export(
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
):
    if output_dir is None:
        output_dir = input_file.parent / input_file.stem

    resource = Resource.from_file(input_file)

    for index in range(resource.file_count):
        resource.export(output_dir, index, separate_chars=separate_chars)


@app.command(help="Generate new resource file from specified folder.")
def generate(
    input_dir: Annotated[Path, typer.Argument(dir_okay=True, readable=True)],
    output_file: Annotated[
        Path | None, typer.Argument(file_okay=True, writable=True)
    ] = None,
    platform: Annotated[
        Platform, typer.Option(..., help="Target platform")
    ] = Platform.UNKNOWN,
):
    if output_file is None:
        output_file = input_dir / f"{input_dir.name}.bin"

    resource = Resource(game=Game.MG1, platform=platform)

    for index in range(RESOURCE_FILES_COUNT):
        resource.add_from_folder(input_dir, index)

    resource.save(output_file)


if __name__ == "__main__":
    app()
