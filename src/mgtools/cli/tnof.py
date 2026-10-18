"""Commands for the TNOF fonts."""

import typer

from mgtools.cli.commands import add_commands
from mgtools.mc.tnof import decode_tnof, encode_tnof, export_tnof, import_tnof

app = typer.Typer(
    help="TNOF fonts (MGS_Font*.raw): the glyphs of the engine's UTF-8 text.",
    no_args_is_help=True,
)
add_commands(
    app,
    suffix=".raw",
    editable_suffix="",
    decode=decode_tnof,
    encode=encode_tnof,
    export=export_tnof,
    import_=import_tnof,
    export_help="Export a font as font.json and a greyscale PNG per glyph.",
    import_help="Import a font from a folder export wrote, sorting its glyphs by code.",
)
