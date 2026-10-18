"""The mgtools command and its groups."""

import typer

from mgtools.cli import cfon, ctxr, gcx, resource, tri

app = typer.Typer(no_args_is_help=True)
app.add_typer(resource.app, name="resource")
app.add_typer(gcx.app, name="gcx")
app.add_typer(ctxr.app, name="ctxr")
app.add_typer(tri.app, name="tri")
app.add_typer(cfon.app, name="cfon")


@app.callback()
def main() -> None:
    """Tools for the PC releases of Metal Gear and Metal Gear 2: Solid Snake."""
