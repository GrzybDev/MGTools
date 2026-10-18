"""Commands for the textures."""

import typer

from mgtools.cli.commands import add_commands
from mgtools.mc.ctxr import (
    decode_texture,
    encode_texture,
    export_texture,
    import_texture,
)

app = typer.Typer(help="Textures (*.ctxr): images and their mipmaps.", no_args_is_help=True)
add_commands(
    app,
    suffix=".ctxr",
    editable_suffix=".png",
    decode=decode_texture,
    encode=encode_texture,
    export=export_texture,
    import_=import_texture,
    export_help=(
        "Export a texture's full-size level as a PNG, with the alpha as stored, and "
        "its settings as JSON next to it."
    ),
    import_help=(
        "Import a texture from a PNG and the JSON next to it, remaking the mipmaps "
        "as the game's converter does."
    ),
    beside=(".json",),
)
