from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from mgtools.bitmap import unpack_2bpp
from mgtools.fileio import read_json
from mgtools.msx.charset import EU_CHARMAP, Charset
from mgtools.msx.font import Font, Page, encode_font
from mgtools.msx.font_editable import export_font, import_font, read_charmap
from mgtools.msx.game import Game
from tests.editing import edit_json
from tests.msx.samples import FONT, PADDED_FONT, double_byte

CHARSET = Charset(Game.MG1, EU_CHARMAP)
FORMS = pytest.mark.parametrize(
    "separate_glyphs", [False, True], ids=["page images", "glyph images"]
)


@FORMS
@pytest.mark.parametrize("font", [FONT, PADDED_FONT], ids=["font", "padded"])
def test_exported_fonts_import_back_unchanged(
    font: Font, separate_glyphs: bool, tmp_path: Path
) -> None:
    export_font(font, CHARSET, tmp_path, separate_glyphs=separate_glyphs)

    imported, charset = import_font(Game.MG1, tmp_path)

    assert encode_font(imported) == encode_font(font)
    assert charset.charmap == EU_CHARMAP


def test_images_hold_glyphs_in_the_cells_of_their_codes(tmp_path: Path) -> None:
    export_font(FONT, CHARSET, tmp_path)

    with Image.open(tmp_path / "font/page0.png") as image:
        assert image.mode == "P"
        assert image.size == (16 * 64, 14 * 24)
        cell = image.crop((64, 2 * 24, 64 + 64, 3 * 24)).tobytes()
        empty = image.crop((128, 2 * 24, 192, 3 * 24)).tobytes()
    rows = [cell[row * 64 : row * 64 + 64] for row in range(24)]
    assert b"".join(row[:7] for row in rows) == pixels_of(FONT.pages[0], 0x41, 24)
    assert {byte for row in rows for byte in row[7:]} == {4}
    assert set(empty) == {5}


def pixels_of(page: Page, code: int, height: int) -> bytes:
    glyph = page.glyphs[code]
    return unpack_2bpp(glyph.data + b"\0", glyph.width * height)


def test_floor_packed_images_show_the_pixels_drawn_from_the_next_glyph(
    tmp_path: Path,
) -> None:
    export_font(FONT, CHARSET, tmp_path)

    with Image.open(tmp_path / "font/page2.png") as image:
        shown = image.crop((64, 2 * 18, 64 + 3, 3 * 18)).tobytes()

    following = unpack_2bpp(FONT.pages[2].glyphs[0x43].data, 2)
    assert shown == pixels_of(FONT.pages[2], 0x41, 18)[:-2] + following


def test_glyph_images_are_named_after_their_characters_and_show_the_drawn_pixels(
    tmp_path: Path,
) -> None:
    # 818B is the double-byte °, which the charmap gives a single byte instead.
    extra = (double_byte(0x818B, 3), double_byte(None, 1))
    font = replace(FONT, double_byte=FONT.double_byte + extra)

    export_font(font, CHARSET, tmp_path, separate_glyphs=True)

    document = read_json(tmp_path / "font.json")
    pages = document["pages"]
    assert [page["glyphs"] for page in pages] == [f"font/page{i}" for i in range(4)]
    assert pages[0]["images"] == {"20": "U+0020.png", "41": "U+0041.png", "A7": "U+010D.png"}
    assert pages[1]["images"]["FF"] == "code-FF.png"
    assert document["double_byte_glyphs"] == "font/page4"
    assert document["double_byte_images"] == [
        "fallback.png",
        "U+3042.png",
        "U+30A2.png",
        "code-818B.png",
        "unused-4.png",
    ]
    named = {f"{page['glyphs']}/{name}" for page in pages for name in page["images"].values()}
    named |= {f"font/page4/{name}" for name in document["double_byte_images"]}
    assert {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.png")} == named
    with Image.open(tmp_path / "font/page0/U+0041.png") as image:
        assert image.size == (7, 24)
        assert image.tobytes() == pixels_of(FONT.pages[0], 0x41, 24)
    with Image.open(tmp_path / "font/page2/U+0041.png") as image:
        following = unpack_2bpp(FONT.pages[2].glyphs[0x43].data, 2)
        assert image.tobytes() == pixels_of(FONT.pages[2], 0x41, 18)[:-2] + following
    assert encode_font(import_font(Game.MG1, tmp_path)[0]) == encode_font(font)


def test_the_double_byte_page_lists_its_glyphs_by_character(tmp_path: Path) -> None:
    export_font(FONT, CHARSET, tmp_path)

    document = read_json(tmp_path / "font.json")
    assert document["double_byte"] == [None, "あ", "ア"]


@FORMS
def test_images_an_editor_turned_into_rgb_are_read_by_their_greys(
    separate_glyphs: bool, tmp_path: Path
) -> None:
    export_font(FONT, CHARSET, tmp_path, separate_glyphs=separate_glyphs)
    for path in (tmp_path / "font").rglob("*.png"):
        with Image.open(path) as image:
            image.convert("RGB").save(path)

    font, _ = import_font(Game.MG1, tmp_path)

    assert encode_font(font) == encode_font(FONT)


def test_the_charmap_of_an_export_can_be_read_alone(tmp_path: Path) -> None:
    export_font(FONT, CHARSET, tmp_path)
    edit_json(tmp_path / "font.json", lambda d: d["charmap"].update({"A0": "ą"}))

    assert read_charmap(tmp_path / "font.json") == EU_CHARMAP | {0xA0: "ą"}

    edit_json(tmp_path / "font.json", lambda d: d["charmap"].update({"41": "ł"}))
    with pytest.raises(ValueError, match=r"font\.json: The charmap names 41"):
        read_charmap(tmp_path / "font.json")


def resize_page(index: int, size: tuple[int, int]) -> Callable[[Path], None]:
    def resize(directory: Path) -> None:
        path = directory / f"font/page{index}.png"
        with Image.open(path) as image:
            image.crop((0, 0, *size)).save(path)

    return resize


def mark_glyph(directory: Path) -> None:
    path = directory / "font/page0.png"
    with Image.open(path) as image:
        image.putpixel((66, 50), 4)
        image.save(path)


def redraw_floor_packed_end(directory: Path) -> int:
    """Change the last pixel of glyph 41 of page 2, which the game takes from 43.

    Args:
        directory: The resource export whose font to change.
    """
    path = directory / "font/page2.png"
    with Image.open(path) as image:
        value = (image.crop((66, 53, 67, 54)).tobytes()[0] + 1) % 4
        image.putpixel((66, 53), value)
        image.save(path)
    return value


def json_edit(edit: Callable[[Any], object]) -> Callable[[Path], None]:
    return lambda directory: edit_json(directory / "font.json", edit)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (
            json_edit(lambda d: d["pages"][0]["widths"].update({"41": 0})),
            r"font\.json: Page 0 gives 41 the width 0, not 1 to 64",
        ),
        (
            json_edit(lambda d: d["pages"][0]["widths"].update({"41": "7"})),
            "the width '7', not 1 to 64",
        ),
        (
            json_edit(lambda d: d["pages"][0]["widths"].update({"1F": 7})),
            r"font\.json: '1F' is not a code from 20 to FF",
        ),
        (
            json_edit(lambda d: d["charmap"].update({"41": "ą"})),
            "The charmap names 41",
        ),
        (
            json_edit(lambda d: d["pages"][2].update(pad_bits={"41": 1})),
            "Page 2 gives 41 pad bits it has no room for",
        ),
        (
            json_edit(lambda d: d["pages"][0].update(pad_bits={"41": 1})),
            "Page 0 gives 41 pad bits it has no room for",
        ),
        (
            json_edit(lambda d: d["pages"][0].update(pad_bits={"42": 1})),
            "Page 0 gives pad bits to 42, which has no glyph",
        ),
        (
            json_edit(lambda d: d["pages"][1].update(v=256)),
            "Page 1 has the constant 256, not a byte",
        ),
        (
            json_edit(lambda d: d["double_byte"].extend([None] * 30)),
            r"page4\.png is 768x24 pixels, not 768x48",
        ),
        (
            json_edit(lambda d: d.update(double_byte=["A"])),
            "Page 4 lists 'A', not a double-byte character",
        ),
        (
            json_edit(lambda d: d.update(double_byte=[None, "あ", "あ"])),
            "Page 4 lists 'あ' twice",
        ),
        (json_edit(lambda d: d.pop("pages")), r"font\.json: missing 'pages'"),
        (resize_page(1, (1024, 100)), r"page1\.png is 1024x100 pixels, not"),
        (
            mark_glyph,
            r"page0\.png, glyph 41: The pixel at \(66, 50\) has palette index 4",
        ),
        (
            redraw_floor_packed_end,
            r"page2\.png, glyph 41: the game draws the last two pixels of a glyph of "
            "floor-packed page 2 from the next glyph",
        ),
    ],
)
def test_font_edits_that_cannot_be_imported_are_reported(
    edit: Callable[[Path], None], message: str, tmp_path: Path
) -> None:
    export_font(FONT, CHARSET, tmp_path)
    edit(tmp_path)

    with pytest.raises(ValueError, match=message):
        import_font(Game.MG1, tmp_path)


def redraw_floor_packed_glyph_end(directory: Path) -> None:
    path = directory / "font/page2/U+0041.png"
    with Image.open(path) as image:
        image.putpixel((2, 17), (image.tobytes()[-1] + 1) % 4)
        image.save(path)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (
            json_edit(lambda d: d["pages"][0]["widths"].update({"A0": 3})),
            r"font\.json: Page 0 gives A0 a width but no image",
        ),
        (
            json_edit(lambda d: d["pages"][0]["images"].update({"42": "U+0042.png"})),
            "Page 0 gives 42 an image but no width",
        ),
        (
            json_edit(lambda d: d["pages"][0]["widths"].update({"41": 8})),
            r"U\+0041\.png is 7x24 pixels, not 8x24",
        ),
        (json_edit(lambda d: d["pages"][1].pop("images")), r"font\.json: missing 'images'"),
        (
            json_edit(lambda d: d["double_byte_images"].pop()),
            "double_byte_images names 2 images for the 3 glyphs of double_byte",
        ),
        (
            redraw_floor_packed_glyph_end,
            r"U\+0041\.png: the game draws the last two pixels of a glyph of "
            "floor-packed page 2 from the next glyph",
        ),
    ],
)
def test_glyph_image_edits_that_cannot_be_imported_are_reported(
    edit: Callable[[Path], None], message: str, tmp_path: Path
) -> None:
    export_font(FONT, CHARSET, tmp_path, separate_glyphs=True)
    edit(tmp_path)

    with pytest.raises(ValueError, match=message):
        import_font(Game.MG1, tmp_path)


def test_glyphs_keep_their_last_pixels_once_their_page_is_not_floor_packed(
    tmp_path: Path,
) -> None:
    export_font(FONT, CHARSET, tmp_path)
    value = redraw_floor_packed_end(tmp_path)
    edit_json(tmp_path / "font.json", lambda d: d["pages"][2].pop("floor_packed"))

    font, _ = import_font(Game.MG1, tmp_path)

    assert not font.pages[2].floor_packed
    assert unpack_2bpp(font.pages[2].glyphs[0x41].data, 3 * 18)[-1] == value
