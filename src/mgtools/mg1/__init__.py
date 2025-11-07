from pathlib import Path
from typing import Annotated

import typer

from mgtools.mg1.constants import RESOURCE_FILES_COUNT
from mgtools.mg1.helpers import export_file
from mgtools.mg1.mappings import LOCALIZABLE_CHUNKS
from mgtools.mg1.resource import Resource

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
    export_all: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Export all resources, including those not classified as 'localizable'.",
        ),
    ] = False,
    separate_chars: Annotated[
        bool,
        typer.Option(
            help="Export font characters as separate images instead of a single atlas.",
        ),
    ] = False,
):
    if output_dir is None:
        output_dir = input_file.parent / input_file.stem

    resource = Resource()

    with input_file.open("rb") as f:
        resource.load(f)

    export_queue = range(resource.file_count) if export_all else LOCALIZABLE_CHUNKS

    for index in export_queue:
        export_file(resource, index, output_dir, separate_chars=separate_chars)


@app.command(help="Generate new resource file from exported resources.")
def generate(
    input_dir: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, readable=True)
    ],
    output_file: Annotated[
        Path | None, typer.Argument(file_okay=True, writable=True)
    ] = None,
):
    resource = Resource()

    for i in range(RESOURCE_FILES_COUNT):
        resource.add(i, input_dir)

    if output_file is None:
        output_file = input_dir / f"{input_dir.name}.bin"

    with output_file.open("wb") as f:
        resource.save(f)


if __name__ == "__main__":
    app()
