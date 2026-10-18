"""The mgtools command and its groups."""

import typer

from mgtools.cli import gcx, resource

app = typer.Typer(no_args_is_help=True)
app.add_typer(resource.app, name="resource")
app.add_typer(gcx.app, name="gcx")


@app.callback()
def main() -> None:
    """Tools for the PC releases of Metal Gear and Metal Gear 2: Solid Snake."""
