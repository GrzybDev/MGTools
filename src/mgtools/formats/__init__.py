import re
from pathlib import Path
from typing import Annotated

import typer

from mgtools.formats.ctxr import export_ctxr, import_ctxr
from mgtools.formats.gcx import compile_gcx, decompile_gcx
from mgtools.formats.gcx.dictionary import load_dictionary
from mgtools.formats.mgs_font import export_mgs_font, import_mgs_font

ctxr = typer.Typer(help="Tools for working with ctxr textures")
gcx = typer.Typer(help="Tools for working with GCX script files")
mgs_font = typer.Typer(
    help="Tools for working with MGS font files (MGS_Font.raw, MGS_Font_nht.raw)"
)


@ctxr.command("export", help="Export ctxr texture(s) to PNG files.")
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


@ctxr.command("import", help="Import PNG file(s) back to ctxr texture(s).")
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


@mgs_font.command(
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


@mgs_font.command(
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


@gcx.command("decompile", help="Decompile GCX file(s) to GCL script.")
def gcx_decompile(
    input_file: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_file: Annotated[
        Path | None, typer.Argument(file_okay=True, writable=True)
    ] = None,
    dictionary: Annotated[
        Path | None,
        typer.Option(
            "--dictionary",
            "-d",
            help="Path to strcode dictionary file for resolving command names.",
        ),
    ] = None,
):
    if output_file is None:
        output_file = input_file.parent / input_file.with_suffix(".gcl")

    dict_data = load_dictionary(dictionary) if dictionary else None
    decompile_gcx(input_file, output_file, dictionary=dict_data)


@gcx.command("compile", help="Compile GCL script back to GCX binary.")
def gcx_compile(
    input_file: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_file: Annotated[
        Path | None, typer.Argument(file_okay=True, writable=True)
    ] = None,
):
    if output_file is None:
        output_file = input_file.parent / input_file.with_suffix(".gcx")

    compile_gcx(input_file, output_file)
