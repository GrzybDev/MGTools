import re
from pathlib import Path
from typing import Annotated

import typer

from mgtools.ctxr import export_ctxr, import_ctxr
from mgtools.enumerators.game import Game
from mgtools.mg1.constants import RESOURCE_SECTION_COUNT as MG1_SECTION_COUNT
from mgtools.mg2.constants import RESOURCE_SECTION_COUNT as MG2_SECTION_COUNT
from mgtools.mgs_font import export_mgs_font, import_mgs_font
from mgtools.resource import Resource

app = typer.Typer(help="Tools for modding PC ports of Metal Gear / Metal Gear 2")
res_app = typer.Typer(
    help="Tools for working with resource files (English.bin, English.raw etc.)"
)
app.add_typer(
    res_app,
    name="resource",
    help="Tools for working with resource files (English.bin, English.raw etc.)",
)
ctxr_app = typer.Typer(help="Tools for working with ctxr textures")
app.add_typer(ctxr_app, name="ctxr", help="Tools for working with ctxr textures")
mgs_font_app = typer.Typer(
    help="Tools for working with MGS font files (MGS_Font_nht.raw)"
)
app.add_typer(
    mgs_font_app,
    name="mgs-font",
    help="Tools for working with MGS font files (MGS_Font.raw, MGS_Font_nht.raw)",
)


@res_app.command(
    "export",
    help="Export resources from specified resource file. (English.bin, English.raw etc.)",
)
def resource_export(
    input_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_dir: Annotated[
        Path | None, typer.Argument(file_okay=False, writable=True)
    ] = None,
    separate_chars: Annotated[
        bool,
        typer.Option(help="Export font glyphs as separate images instead of an atlas."),
    ] = False,
):
    if output_dir is None:
        output_dir = input_file.parent / input_file.stem

    resource = Resource.from_file(input_file)
    resource.save_metadata(output_dir)

    for index in range(resource.section_count):
        resource.export(output_dir, index, separate_chars=separate_chars)


@res_app.command("generate", help="Generate new resource file from specified folder.")
def resource_generate(
    input_dir: Annotated[Path, typer.Argument(dir_okay=True, readable=True)],
    output_file: Annotated[
        Path | None, typer.Argument(file_okay=True, writable=True)
    ] = None,
):
    game = Resource.detect_game(input_dir)

    if game == Game.MG1:
        section_count = MG1_SECTION_COUNT
    else:
        section_count = MG2_SECTION_COUNT

    if output_file is None:
        output_file = input_dir / f"{input_dir.name}.bin"

    resource = Resource(game=game)

    for index in range(section_count):
        resource.add_from_folder(input_dir, index)

    resource.save(output_file)


@ctxr_app.command("export", help="Export ctxr texture(s) to PNG files.")
def ctxr_export(
    input_file_or_dir: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_dir: Annotated[
        Path | None, typer.Argument(file_okay=False, writable=True)
    ] = None,
):
    if output_dir is None:
        output_dir = input_file_or_dir.parent

    output_dir.mkdir(parents=True, exist_ok=True)

    if input_file_or_dir.is_file():
        output_file = output_dir / f"{input_file_or_dir.stem}.png"
        export_ctxr(input_file_or_dir, output_file)
    else:
        for ctxr_file in input_file_or_dir.glob("*.ctxr"):
            output_file = output_dir / f"{ctxr_file.stem}.png"
            export_ctxr(ctxr_file, output_file)


@ctxr_app.command("import", help="Import PNG file(s) back to ctxr texture(s).")
def ctxr_import(
    input_file_or_dir: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_dir: Annotated[
        Path | None, typer.Argument(file_okay=False, writable=True)
    ] = None,
):
    if output_dir is None:
        output_dir = input_file_or_dir.parent

    output_dir.mkdir(parents=True, exist_ok=True)

    if input_file_or_dir.is_file():
        import_ctxr(input_file_or_dir, output_dir)
    else:
        for png_file in input_file_or_dir.glob("*.png"):
            if re.search(r"\.mip\d+\.png$", png_file.name):
                continue

            import_ctxr(png_file, output_dir)


@mgs_font_app.command(
    "export", help="Export MGS font file to a folder with glyph images and metadata."
)
def mgs_font_export(
    input_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_dir: Annotated[
        Path | None, typer.Argument(file_okay=False, writable=True)
    ] = None,
):
    if output_dir is None:
        output_dir = input_file.parent / input_file.stem

    export_mgs_font(input_file, output_dir)


@mgs_font_app.command(
    "import", help="Import glyph images and metadata back into MGS font file."
)
def mgs_font_import(
    input_dir: Annotated[
        Path, typer.Argument(exists=True, dir_okay=True, readable=True)
    ],
    output_file: Annotated[
        Path | None, typer.Argument(file_okay=True, writable=True)
    ] = None,
):
    if output_file is None:
        output_file = input_dir.parent / f"{input_dir.name}.raw"

    import_mgs_font(input_dir, output_file)
