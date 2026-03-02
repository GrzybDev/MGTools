import typer

from mgtools import formats, resource

app = typer.Typer(help="Tools for modding PC ports of Metal Gear / Metal Gear 2")
app.add_typer(
    resource.app,
    name="resource",
    help="Tools for working with resource files (English.bin, English.raw etc.)",
)
app.add_typer(formats.ctxr, name="ctxr", help="Tools for working with ctxr textures")
app.add_typer(
    formats.gcx,
    name="gcx",
    help="Tools for working with GCX script files (Game Command Language)",
)
app.add_typer(
    formats.mgs_font,
    name="mgs-font",
    help="Tools for working with MGS font files (MGS_Font.raw, MGS_Font_nht.raw)",
)
