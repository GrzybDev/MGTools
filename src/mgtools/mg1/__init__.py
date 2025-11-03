from pathlib import Path
from typing import Annotated

import typer

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
):
    resource = Resource()

    with input_file.open("rb") as f:
        resource.load(f)


if __name__ == "__main__":
    app()
