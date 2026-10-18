"""The mgtools command and its groups."""

import typer

from mgtools.cli import resource

app = typer.Typer(no_args_is_help=True)
app.add_typer(resource.app, name="resource")


@app.callback()
def main() -> None:
    """Tools for the PC releases of Metal Gear and Metal Gear 2: Solid Snake."""
