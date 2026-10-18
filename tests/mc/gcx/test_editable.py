from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image
from translate.storage.pypo import pofile

from mgtools.bitmap import pack_2bpp, unpack_2bpp
from mgtools.mc.gcx.editable import GLYPHS, LISTING, export_script, import_script
from mgtools.mc.gcx.nodes import Block, Call, Int, String
from mgtools.mc.gcx.script import (
    GLYPH_BYTES,
    DataResource,
    Proc,
    Script,
    StringResource,
)
from mgtools.translation import TranslationFormat

# 16 glyphs fill the first row of the image, a blank 17th starts the second.
GLYPHS_DATA = b"".join(bytes([i * 17]) * GLYPH_BYTES for i in [*range(16), 0])
SCRIPT = Script(
    bluepoint=True,
    timestamp=1,
    seed=0,
    procs=(Proc(1, Block((Call(1),))),),
    main=Block(()),
    resources=(
        StringResource(b"Save?\n", "Save?\n"),
        DataResource((Int(3), String(b"KNIFE"))),
        StringResource(b"\x8c\x01 ok", "Key ok"),
    ),
    glyphs=GLYPHS_DATA,
)


def export(directory: Path, fmt: TranslationFormat = TranslationFormat.PO) -> None:
    export_script(SCRIPT, directory, fmt, original="test.gcx", source_language="en")


@pytest.mark.parametrize("fmt", list(TranslationFormat))
def test_a_script_reads_back_from_its_directory(tmp_path: Path, fmt: TranslationFormat) -> None:
    export(tmp_path, fmt)

    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        [GLYPHS, LISTING, f"text{fmt.suffix}"]
    )
    assert import_script(tmp_path) == SCRIPT


def test_translations_replace_the_utf8_texts_and_leave_the_ps2_strings(
    tmp_path: Path,
) -> None:
    export(tmp_path)
    path = tmp_path / "text.po"
    store = pofile.parsestring(path.read_bytes())
    unit = next(unit for unit in store.units if unit.getcontext() == "res:0")
    unit.target = "Zapisać grę?\n"
    path.write_bytes(bytes(store))

    resources = import_script(tmp_path).resources

    assert resources[0] == StringResource(b"Save?\n", "Zapisać grę?\n")
    assert resources[1:] == SCRIPT.resources[1:]


def test_notes_give_the_ps2_text_where_it_differs(tmp_path: Path) -> None:
    export(tmp_path)

    units = pofile.parsestring((tmp_path / "text.po").read_bytes()).units[1:]

    assert [unit.getnotes("developer") for unit in units] == ["", "PS2 text: {8C01} ok"]


def test_glyphs_are_laid_out_16_to_a_row_and_edits_are_read_back(
    tmp_path: Path,
) -> None:
    export(tmp_path)
    with Image.open(tmp_path / GLYPHS) as image:
        assert image.size == (16 * 24, 2 * 24)
        edited = image.convert("RGB")
    edited.putpixel((24 + 1, 0), (255, 255, 255))
    edited.save(tmp_path / GLYPHS)

    glyphs = import_script(tmp_path).glyphs

    pixels = bytearray(unpack_2bpp(GLYPHS_DATA[GLYPH_BYTES:], 24 * 24))
    pixels[1] = 3
    assert glyphs[GLYPH_BYTES : 2 * GLYPH_BYTES] == pack_2bpp(bytes(pixels))
    assert glyphs[:GLYPH_BYTES] + glyphs[2 * GLYPH_BYTES :] == (
        GLYPHS_DATA[:GLYPH_BYTES] + GLYPHS_DATA[2 * GLYPH_BYTES :]
    )


@pytest.mark.parametrize(
    ("image", "message"),
    [
        (Image.new("L", (10, 10)), r"glyphs\.png is 10x10 pixels, not 384x48"),
        (
            Image.new("RGB", (384, 48), (255, 0, 0)),
            r"glyphs\.png, glyph 0: The pixel at \(0, 0\) is not one of the four greys",
        ),
    ],
)
def test_glyph_images_the_glyphs_cannot_come_from_are_refused(
    tmp_path: Path, image: Image.Image, message: str
) -> None:
    export(tmp_path)
    image.save(tmp_path / GLYPHS)

    with pytest.raises(ValueError, match=message):
        import_script(tmp_path)


def test_a_script_without_texts_or_glyphs_is_only_a_listing(tmp_path: Path) -> None:
    plain = replace(SCRIPT, bluepoint=False, resources=(StringResource(b"Yes"),), glyphs=b"")

    export_script(plain, tmp_path, TranslationFormat.PO, original="a", source_language="en")

    assert [path.name for path in tmp_path.iterdir()] == [LISTING]
    assert import_script(tmp_path) == plain


def test_listing_mistakes_name_the_file(tmp_path: Path) -> None:
    (tmp_path / LISTING).write_text("gcx\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"script\.gcl: Line 2: expected bluepoint"):
        import_script(tmp_path)
