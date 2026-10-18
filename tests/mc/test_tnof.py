from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from mgtools.errors import FormatError
from mgtools.fileio import read_json, write_json
from mgtools.mc.tnof import (
    Glyph,
    TnofFont,
    decode_tnof,
    encode_tnof,
    export_tnof,
    import_tnof,
)

FONT = TnofFont(
    (40, 40, 4),
    (
        Glyph(0x41, 2, 1, -1, 3, 5, b"\x00\xff"),
        Glyph(0x42, 0, 0, 0, 0, 4, b""),
    ),
)
FONT_BYTES = bytes.fromhex(
    "544e4f46 28000000 28000000 04000000 18000000 02000000"
    "41000000 28000000 42000000 2f000000"
    "0201ff0305 00ff 0000000004"
)
REPEATED = TnofFont(
    (40, 40, 4),
    (
        Glyph(0x27, 1, 1, 0, 0, 3, b"\x10"),
        Glyph(0x27, 1, 2, 0, 0, 3, b"\x20\x30"),
        Glyph(0x3000, 0, 1, 0, 0, 40, b""),
    ),
)


def _edit_document(directory: Path, edit: dict[str, Any]) -> None:
    path = directory / "font.json"
    document = read_json(path)
    document["glyphs"][-1] = {
        key: value for key, value in (document["glyphs"][-1] | edit).items() if value is not None
    }
    write_json(path, document)


def test_a_font_is_encoded_as_its_table_and_records_and_decoded_back() -> None:
    assert encode_tnof(FONT) == FONT_BYTES
    assert decode_tnof(FONT_BYTES) == FONT


def test_every_entry_of_a_repeated_code_points_at_its_last_record() -> None:
    data = encode_tnof(REPEATED)

    first_record = 0x18 + 8 * 3
    second_record = first_record + 6
    assert data[0x18:0x28] == bytes.fromhex(f"27000000 {second_record:02x}000000") * 2
    assert decode_tnof(data) == REPEATED


@pytest.mark.parametrize(
    ("data", "message"),
    [
        pytest.param(b"FONT" + FONT_BYTES[4:], "Not a TNOF font", id="magic"),
        pytest.param(
            FONT_BYTES[:16] + b"\x20" + FONT_BYTES[17:],
            "table is at offset 32",
            id="table offset",
        ),
        pytest.param(FONT_BYTES + b"\x00", "1 bytes follow the last glyph record", id="extra"),
        pytest.param(FONT_BYTES[:-1], "Unexpected end of data", id="cut"),
        pytest.param(
            FONT_BYTES[:0x1C] + b"\x2f" + FONT_BYTES[0x1D:],
            r"Entry 0 \(U\+0041\) points at offset 47",
            id="record offset",
        ),
    ],
)
def test_malformed_fonts_are_reported(data: bytes, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        decode_tnof(data)


@pytest.mark.parametrize(
    ("glyph", "message"),
    [
        (Glyph(0x41, 2, 2, 0, 0, 5, b"\x00"), r"U\+0041 has 1 pixels for 2 by 2"),
        (Glyph(0x41, 1, 1, 0, 128, 5, b"\x00"), r"U\+0041 needs .* bearings from -128"),
        (Glyph(0x41, 0, 0, 0, 0, 256, b""), r"U\+0041 needs a size and an advance"),
    ],
)
def test_glyphs_a_record_cannot_hold_are_refused(glyph: Glyph, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        encode_tnof(TnofFont((40, 40, 4), (glyph,)))


def test_an_exported_font_imports_back_with_its_unused_records(tmp_path: Path) -> None:
    export_tnof(REPEATED, tmp_path)

    assert sorted(path.name for path in (tmp_path / "glyphs").iterdir()) == [
        "U+0027.png",
        "U+0027.unused1.png",
    ]
    assert import_tnof(tmp_path) == REPEATED


def test_glyphs_added_to_the_document_are_sorted_by_code(tmp_path: Path) -> None:
    export_tnof(FONT, tmp_path)
    document_path = tmp_path / "font.json"
    document = read_json(document_path)
    document["glyphs"].insert(0, {"code": "U+0104", "bearing_x": 1, "bearing_y": -2, "advance": 9})
    write_json(document_path, document)
    Image.frombytes("L", (3, 1), b"\x01\x02\x03").save(tmp_path / "glyphs" / "U+0104.png")

    font = import_tnof(tmp_path)

    assert [glyph.code for glyph in font.glyphs] == [0x41, 0x42, 0x104]
    assert font.glyphs[2] == Glyph(0x104, 3, 1, 1, -2, 9, b"\x01\x02\x03")


def test_a_glyph_drawn_on_transparency_covers_what_it_shows_on_black(
    tmp_path: Path,
) -> None:
    export_tnof(FONT, tmp_path)
    image = Image.new("RGBA", (3, 1), (255, 255, 255, 0))
    image.putpixel((1, 0), (255, 255, 255, 255))
    image.putpixel((2, 0), (200, 200, 200, 255))
    image.save(tmp_path / "glyphs" / "U+0041.png")

    font = import_tnof(tmp_path)

    assert font.glyphs[0].pixels == bytes([0, 255, 200])


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        ({"code": "0042"}, r"'0042' is not a code point written as U\+XXXX"),
        ({"width": 4, "height": 2}, r"U\+0042 has no image, so it must be 0 wide"),
    ],
)
def test_mistakes_in_the_document_are_reported_with_its_path(
    tmp_path: Path, edit: dict[str, Any], message: str
) -> None:
    export_tnof(FONT, tmp_path)
    _edit_document(tmp_path, edit)

    with pytest.raises(ValueError, match=rf"font\.json: {message}"):
        import_tnof(tmp_path)
