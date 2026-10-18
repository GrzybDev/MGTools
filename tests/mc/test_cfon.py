import struct
from dataclasses import replace
from pathlib import Path

import pytest

from mgtools.errors import FormatError
from mgtools.fileio import read_json
from mgtools.mc.cfon import (
    ConsoleFont,
    decode_font,
    encode_font,
    export_font,
    import_font,
)

ASCII = {chr(code): 0 for code in range(128)}
FONT = ConsoleFont(
    glyphs=((0, 0, 0, 0), (0.25, 0.5, 0.375, 0.625), (0.5, 0.5, 0.625, 0.75)),
    characters=ASCII | {"A": 1, "ÿ": 1, "é": 2, "™": 1, "😀": 2},
    texture="$/fonts/****/console.ctxr",
)


def arrays(data: bytes) -> list[tuple[int, ...]]:
    """Return the arrays after the glyph boxes of an encoded font.

    Args:
        data: The encoded font.
    """
    offset = 0x18 + 4 * struct.unpack_from(">I", data, 0x14)[0]
    found = []
    for fmt in "HHHHHIHIH":
        (count,) = struct.unpack_from(">I", data, offset)
        found.append(struct.unpack_from(f">{count}{fmt}", data, offset + 4))
        offset += 4 + struct.calcsize(f">{count}{fmt}")
    return found


def test_characters_are_mapped_by_the_length_of_their_utf_8_sequences() -> None:
    data = encode_font(FONT)

    assert data[:0x18] == b"FONT" + bytes.fromhex("00000005 0000000a 00000002 41500000 0000000c")
    found = arrays(data)
    assert found[0] == (0, 0, 0)
    assert found[1] == tuple(1 if code == 0x41 else 0 for code in range(128))
    assert found[2:8] == [
        (2, 1),
        (0xC3A9, 0xC3BF),
        (1,),
        (0xE284A2,),
        (2,),
        (0xF09F9880,),
    ]
    assert found[8] == (1,) * 128
    assert data.endswith(b"\x19$/fonts/****/console.ctxr")
    assert decode_font(data) == FONT


@pytest.mark.parametrize(
    ("characters", "message"),
    [
        ({"a": 0}, "Every ASCII character"),
        (ASCII | {"é": 3}, "'é' uses glyph 3, but the font has 3"),
        (ASCII | {"ab": 1}, "'ab' is not one character"),
    ],
)
def test_characters_without_a_glyph_are_refused(characters: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        encode_font(replace(FONT, characters=characters))


@pytest.mark.parametrize(
    ("offset", "message"),
    [(4, "Not a console font"), (-30, "cannot keep, at offset")],
)
def test_fonts_this_tool_cannot_rebuild_are_refused(offset: int, message: str) -> None:
    data = bytearray(encode_font(FONT))
    data[offset] ^= 1

    with pytest.raises(FormatError, match=message):
        decode_font(bytes(data))


def test_the_json_maps_each_character_to_its_glyph(tmp_path: Path) -> None:
    path = tmp_path / "console.json"

    export_font(FONT, path)

    document = read_json(path)
    assert document["glyphs"][1] == [0.25, 0.5, 0.375, 0.625]
    assert list(document["characters"])[-4:] == ["é", "ÿ", "™", "😀"]
    assert import_font(path) == FONT
