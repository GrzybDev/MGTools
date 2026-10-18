"""Commands for the console fonts."""

import typer

from mgtools.cli.commands import add_commands
from mgtools.mc.cfon import decode_font, encode_font, export_font, import_font

app = typer.Typer(help="Console fonts (*.cfon): the glyph of each character.", no_args_is_help=True)
add_commands(
    app,
    suffix=".cfon",
    editable_suffix=".json",
    decode=decode_font,
    encode=encode_font,
    export=export_font,
    import_=import_font,
    export_help=(
        "Export the glyph boxes of a console font and the glyph of each character as JSON."
    ),
    import_help="Import a console font from JSON.",
)
