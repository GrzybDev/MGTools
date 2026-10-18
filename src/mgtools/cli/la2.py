"""Commands for the 2D layouts."""

import typer

from mgtools.cli.commands import add_commands
from mgtools.mc.la2.codec import decode_layout, encode_layout
from mgtools.mc.la2.editable import export_layout, import_layout

app = typer.Typer(
    help="2D layouts (*.la2): the scenes of HUDs and menus, with their texts.",
    no_args_is_help=True,
)
add_commands(
    app,
    suffix=".la2",
    editable_suffix=".json",
    decode=decode_layout,
    encode=encode_layout,
    export=export_layout,
    import_=import_layout,
    export_help=(
        "Export a layout as JSON, with its texts in Latin-1 and its offsets replaced by indices."
    ),
    import_help=(
        "Import a layout from JSON, checking that the font of each text has a glyph "
        "for each of its characters."
    ),
)
