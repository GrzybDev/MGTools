"""The mgtools command and its groups."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Tools for the PC releases of Metal Gear and Metal Gear 2: Solid Snake."""
