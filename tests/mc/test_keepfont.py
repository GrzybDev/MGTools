from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from mgtools.bitmap import grey_image
from mgtools.errors import FormatError
from mgtools.mc.keepfont import (
    Keepfont,
    LatinGlyph,
    decode_keepfont,
    encode_keepfont,
    export_keepfont,
    import_keepfont,
)
from tests.editing import edit_json

FONT = Keepfont(
    0x800,
    (
        LatinGlyph(1, 0, bytes([3]) * 24),
        LatinGlyph(2, 0x800, bytes([0, 1, 2, 3]) * 12),
    ),
    (bytes([2]) + bytes(575),),
)
FONT_BYTES = (
    bytes.fromhex("1000 0008 22000000 0000 0000 0600 1008")
    + b"\xff" * 6
    + b"\x1b" * 12
    + b"\x80"
    + bytes(143 + 14)
)


def test_a_font_is_encoded_with_its_table_and_padding_and_decoded_back() -> None:
    assert encode_keepfont(FONT) == FONT_BYTES
    assert decode_keepfont(FONT_BYTES) == FONT


def test_bytes_no_entry_points_at_are_kept_after_their_glyph() -> None:
    first, second = FONT.latin
    font = replace(
        FONT,
        latin=(replace(first, unused=b"\xaa\xbb"), replace(second, unused=b"\xcc")),
    )

    data = encode_keepfont(font)

    assert data[:16] == bytes.fromhex("1000 0008 25000000 0000 0000 0800 1008")
    assert decode_keepfont(data) == font


@pytest.mark.parametrize(
    ("offset", "patch", "message"),
    [
        (0, "0f00", "table cannot end at offset 15"),
        (8, "0200", "glyph of 0x20 starts at 18, not at 16"),
        (12, "0400", "glyph of 0x21 starts at 20, not at 22"),
        (4, "20000000", "Latin glyphs end at 34, after 32"),
        (len(FONT_BYTES) - 1, "01", "should end with 14 zeros after the kana at 178"),
    ],
)
def test_malformed_fonts_are_reported(offset: int, patch: str, message: str) -> None:
    replacement = bytes.fromhex(patch)
    data = FONT_BYTES[:offset] + replacement + FONT_BYTES[offset + len(replacement) :]

    with pytest.raises(FormatError, match=message):
        decode_keepfont(data)


@pytest.mark.parametrize(
    ("latin", "message"),
    [
        ((LatinGlyph(65, 0, bytes(24 * 65)),), "0x20 must be 1 to 64 wide and 24 high"),
        ((LatinGlyph(1, 0, bytes(23)),), "0x20 must be 1 to 64 wide and 24 high"),
        ((LatinGlyph(1, 0x10, bytes(24)),), "flags of 0x20 overlap the width bits"),
        ((LatinGlyph(1, 0, bytes(24)),) * 225, "for the 224 byte codes 0x20 to 0xff"),
        ((LatinGlyph(64, 0, bytes(24 * 64)),) * 172, "0xcb starts past the 64 KiB"),
    ],
)
def test_glyphs_the_table_cannot_describe_are_refused(
    latin: tuple[LatinGlyph, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        encode_keepfont(replace(FONT, latin=latin))


def test_an_exported_font_imports_back(tmp_path: Path) -> None:
    font = replace(FONT, latin=(FONT.latin[0], replace(FONT.latin[1], unused=b"\x01")))

    export_keepfont(font, tmp_path)

    assert (tmp_path / "latin" / "21.png").is_file()
    with Image.open(tmp_path / "kana.png") as kana:
        assert kana.size == (24, 24)
    assert import_keepfont(tmp_path) == font


def test_a_latin_glyph_takes_the_width_of_its_image(tmp_path: Path) -> None:
    export_keepfont(FONT, tmp_path)
    grey_image(bytes([1, 2, 3]) * 24, (3, 24)).save(tmp_path / "latin" / "20.png")

    font = import_keepfont(tmp_path)

    assert font.latin[0] == LatinGlyph(3, 0, bytes([1, 2, 3]) * 24)
    assert decode_keepfont(encode_keepfont(font)) == font


def test_a_latin_image_must_be_24_pixels_high(tmp_path: Path) -> None:
    export_keepfont(FONT, tmp_path)
    grey_image(bytes(25), (1, 25)).save(tmp_path / "latin" / "21.png")

    with pytest.raises(ValueError, match=r"21\.png must be 24 pixels high"):
        import_keepfont(tmp_path)


def test_the_kana_image_must_be_a_column_of_24_pixel_squares(tmp_path: Path) -> None:
    export_keepfont(FONT, tmp_path)
    grey_image(bytes(48 * 24), (48, 24)).save(tmp_path / "kana.png")

    with pytest.raises(ValueError, match=r"kana\.png must be a column of 24-pixel"):
        import_keepfont(tmp_path)


def test_colours_other_than_the_greys_are_reported_with_their_image(
    tmp_path: Path,
) -> None:
    export_keepfont(FONT, tmp_path)
    image = Image.new("RGB", (1, 24))
    image.putpixel((0, 5), (255, 0, 0))
    image.save(tmp_path / "latin" / "20.png")

    with pytest.raises(ValueError, match=r"20.png: The pixel at \(0, 5\)"):
        import_keepfont(tmp_path)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (
            lambda document: document["latin"].reverse(),
            "It lists 0x21 where 0x20 belongs",
        ),
        (
            lambda document: document["latin"][0].update(flags="8"),
            "The flags '8' of 0x20 are not a 16-bit word",
        ),
    ],
)
def test_the_document_gives_the_flags_of_each_code_in_order(
    tmp_path: Path, edit: Callable[[Any], object], message: str
) -> None:
    export_keepfont(FONT, tmp_path)
    edit_json(tmp_path / "keepfont.json", edit)

    with pytest.raises(ValueError, match=rf"keepfont\.json: {message}"):
        import_keepfont(tmp_path)
