"""Commands for the keepfonts."""

import typer

from mgtools.cli.commands import add_commands
from mgtools.mc.keepfont import (
    decode_keepfont,
    encode_keepfont,
    export_keepfont,
    import_keepfont,
)

app = typer.Typer(
    help=("Keepfonts (keepfont*.raw): 2-bit Latin glyphs in the Mac OS Roman layout and kana."),
    no_args_is_help=True,
)
add_commands(
    app,
    suffix=".raw",
    editable_suffix="",
    decode=decode_keepfont,
    encode=encode_keepfont,
    export=export_keepfont,
    import_=import_keepfont,
    export_help="Export a font as keepfont.json, a PNG per Latin glyph and kana.png.",
    import_help=(
        "Import a font from a folder export wrote; a Latin glyph is as wide as its "
        "PNG, 1 to 64 pixels, and 24 high."
    ),
)
