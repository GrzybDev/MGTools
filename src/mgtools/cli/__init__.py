"""The mgtools command and its groups."""

import os
import sys

import typer

from mgtools.cli import (
    cfon,
    ctxr,
    files,
    gcx,
    keepfont,
    la2,
    resource,
    sdx,
    stov,
    tnof,
    tri,
)

app = typer.Typer(no_args_is_help=True)
app.add_typer(resource.app, name="resource")
app.add_typer(gcx.app, name="gcx")
app.add_typer(ctxr.app, name="ctxr")
app.add_typer(tri.app, name="tri")
app.add_typer(la2.app, name="la2")
app.add_typer(cfon.app, name="cfon")
app.add_typer(tnof.app, name="tnof")
app.add_typer(keepfont.app, name="keepfont")
app.add_typer(stov.app, name="stov")
app.add_typer(sdx.app, name="sdx")
app.command(name="files")(files.files)


@app.callback()
def main() -> None:
    """Tools for the PC releases of Metal Gear and Metal Gear 2: Solid Snake."""


def run() -> None:
    """Run the mgtools command with the arguments it was started with."""
    args = sys.argv[1:]
    if os.name == "nt":
        # On Windows, Click expands ~, variables and wildcards in the arguments, as the shells there
        # leave wildcards to the program. Its wildcards would split the pattern of a texture
        # command into many arguments, so only ~ and variables are expanded, the way Click does:
        # on strings, as not every argument is a path.
        args = [os.path.expandvars(os.path.expanduser(arg)) for arg in args]  # noqa: PTH111
    app(args)
