"""Commands for the PS2 sprite atlases."""

import typer

from mgtools.cli.commands import add_commands
from mgtools.mc.tri import decode_atlas, encode_atlas, export_atlas, import_atlas

app = typer.Typer(
    help="PS2 sprite atlases (*.tri): the GS registers of each sprite.",
    no_args_is_help=True,
)
add_commands(
    app,
    suffix=".tri",
    editable_suffix=".json",
    decode=decode_atlas,
    encode=encode_atlas,
    export=export_atlas,
    import_=import_atlas,
    export_help="Export the sprites of an atlas and their GS registers as JSON.",
    import_help=(
        "Import an atlas from JSON, deriving each sprite's texture coordinates from "
        "its TEX0 and CLAMP registers."
    ),
)
