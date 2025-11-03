import typer

from mgtools import mg1

app = typer.Typer(help="Tools for modding PC ports of Metal Gear / Metal Gear 2")

app.add_typer(
    typer_instance=mg1.app, name="mg1", help="Tools for modding PC ports of Metal Gear"
)


if __name__ == "__main__":
    app()
