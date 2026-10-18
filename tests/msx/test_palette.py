from pathlib import Path

import pytest

from mgtools.errors import FormatError
from mgtools.msx.palette import (
    colour_name,
    decode_palette,
    encode_palette,
    export_palettes,
    import_palettes,
    parse_colour,
)


def test_colours_are_stored_as_blue_green_red_and_a_zero_byte() -> None:
    data = bytes.fromhex("ff000000 10204000")

    assert decode_palette(data) == [(0, 0, 255), (64, 32, 16)]
    assert encode_palette([(0, 0, 255), (64, 32, 16)]) == data


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("00000000 00000001", "Colour 1 of the palette has 1 in its unused byte"),
        ("000000", "4 bytes per colour, which 3 bytes are not"),
    ],
)
def test_malformed_palettes_are_refused(data: str, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        decode_palette(bytes.fromhex(data))


def test_colours_are_named_as_hex_triplets() -> None:
    assert colour_name((255, 0, 128)) == "#ff0080"
    assert parse_colour("#FF0080") == (255, 0, 128)


@pytest.mark.parametrize("name", ["#fff", "ff0080", "#gg0080", 0xFF0080, None])
def test_other_colour_names_are_refused(name: object) -> None:
    with pytest.raises(ValueError, match="is not a colour written #rrggbb"):
        parse_colour(name)


def test_palettes_round_trip_through_json(tmp_path: Path) -> None:
    palettes = [[(255, 0, 255), (0, 0, 0)], []]

    export_palettes(palettes, tmp_path / "palettes.json")

    assert import_palettes(tmp_path / "palettes.json") == palettes


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ('{"colours": []}', r"palettes\.json: Not a list of palettes"),
        ('[["#000000"], ["#00000"]]', "Palette 1: '#00000' is not a colour"),
        ('[["#000000"' + ', "#000000"' * 256 + "]]", "257 colours, more than 256"),
    ],
)
def test_edited_palettes_are_checked(tmp_path: Path, value: str, message: str) -> None:
    path = tmp_path / "palettes.json"
    path.write_text(value)

    with pytest.raises(ValueError, match=message):
        import_palettes(path)
