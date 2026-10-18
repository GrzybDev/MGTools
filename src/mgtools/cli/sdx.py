"""Commands for the sound banks."""

import typer

from mgtools.cli.commands import add_commands
from mgtools.mc.sdx import decode_sdx, encode_sdx, export_sdx, import_sdx

app = typer.Typer(help="Sound banks (*.sdx): the sound effects of a stage.", no_args_is_help=True)
add_commands(
    app,
    suffix=".sdx",
    editable_suffix="",
    decode=decode_sdx,
    encode=encode_sdx,
    export=export_sdx,
    import_=import_sdx,
    export_help="Export sound banks as sdx.json, raw SPU-ADPCM waves and MIDI files.",
    import_help="Import sound banks from a folder export wrote.",
)
