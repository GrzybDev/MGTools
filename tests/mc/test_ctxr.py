import struct
from pathlib import Path

import pytest
from PIL import Image

from mgtools.errors import FormatError
from mgtools.fileio import read_json
from mgtools.mc.ctxr import (
    Texture,
    decode_texture,
    encode_texture,
    export_texture,
    import_texture,
    mipmaps,
)


def grey(*values: int) -> bytes:
    return b"".join(bytes((value, value, value, 255)) for value in values)


BGRA = bytes([10, 20, 30, 255, 40, 50, 60, 128, 1, 2, 3, 255, 200, 100, 0, 255])
TEXTURE = Texture(7, 2, 2, (BGRA, mipmaps(BGRA, 2, 2)[0]))


def test_the_header_holds_the_colour_range_of_level_0_and_levels_align_to_32() -> None:
    data = encode_texture(TEXTURE)

    assert data[:0x10] == b"TXTR" + bytes.fromhex("00000007 0002 0002 0001 0000")
    assert data[0x12] == 1
    assert data[0x17:0x1F] == bytes([0, 2, 1, 128, 60, 100, 200, 255])
    assert data[0x26] == 2
    assert data[0x80:0x94] == struct.pack(">I", 16) + BGRA
    assert data[0xA0:0xA8] == struct.pack(">I", 4) + TEXTURE.levels[1]
    assert len(data) == 0xC0
    assert decode_texture(data) == TEXTURE


def test_version_5_keeps_its_level_count_earlier() -> None:
    texture = Texture(5, 1, 1, (grey(7),))

    data = encode_texture(texture)

    assert data[0x12] == 0
    assert data[0x1F:0x24] == bytes([0, 0, 0, 0, 1])
    assert decode_texture(data) == texture


def test_mipmaps_floor_the_means_of_level_0_blocks_down_to_1x1_on_power_of_two_sides() -> None:
    square = grey(2, 2, 2, 2, 2, 1, 2, 1, 2, 2, 3, 3, 2, 1, 3, 2)
    oblong = grey(0, 1, 2, 3, 4, 5, 6, 7)

    # Averaging level 1 instead of level 0 would give 1 for the last level.
    assert mipmaps(square, 4, 4) == [grey(1, 1, 1, 2), grey(2)]
    assert mipmaps(oblong, 8, 1) == [grey(0, 2, 4, 6), grey(1, 5), grey(3)]
    with pytest.raises(ValueError, match=r"power-of-two sides .* not 3x2"):
        mipmaps(grey(0, 0, 0, 0, 0, 0), 3, 2)


def test_the_png_holds_the_texels_in_rgba_with_the_alpha_as_stored(
    tmp_path: Path,
) -> None:
    export_texture(Texture(7, 1, 1, (bytes([1, 2, 3, 128]),)), tmp_path / "t.png")

    with Image.open(tmp_path / "t.png") as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (3, 2, 1, 128)
    assert read_json(tmp_path / "t.json") == {
        "version": 7,
        "mipmaps": False,
    }


RED = bytes([0, 0, 255, 255])
# The game's converter wrote a few mipmap texels one lower than computed.
SHIPPED = bytes([0, 0, 255, 254])


def test_shipped_mipmap_texels_that_differ_from_the_computed_ones_survive(
    tmp_path: Path,
) -> None:
    texture = Texture(7, 2, 2, (RED * 4, SHIPPED))

    export_texture(texture, tmp_path / "t.png")

    settings = read_json(tmp_path / "t.json")
    assert settings["mipmap_overrides"] == [
        {"level": 1, "x": 0, "y": 0, "computed": "#ff0000ff", "shipped": "#ff0000fe"}
    ]
    assert encode_texture(import_texture(tmp_path / "t.png")) == encode_texture(texture)


def test_an_edit_of_level_0_remakes_the_mipmaps_and_the_header(tmp_path: Path) -> None:
    export_texture(Texture(7, 2, 2, (RED * 4, SHIPPED)), tmp_path / "t.png")
    with Image.open(tmp_path / "t.png") as image:
        image.putpixel((0, 0), (255, 0, 0, 0))
        image.save(tmp_path / "t.png")

    texture = import_texture(tmp_path / "t.png")

    assert texture.levels[1] == bytes([0, 0, 255, 191])
    data = encode_texture(texture)
    assert data[0x12] == 1
    assert data[0x17:0x1F] == bytes([255, 0, 0, 0, 255, 0, 0, 255])


def test_an_edit_elsewhere_keeps_a_shipped_mipmap_texel(tmp_path: Path) -> None:
    export_texture(Texture(7, 4, 1, (RED * 4, SHIPPED + RED, RED)), tmp_path / "t.png")
    with Image.open(tmp_path / "t.png") as image:
        image.putpixel((3, 0), (0, 0, 255, 255))
        image.save(tmp_path / "t.png")

    texture = import_texture(tmp_path / "t.png")

    assert texture.levels[1] == SHIPPED + bytes([127, 0, 127, 255])
    assert texture.levels[2] == bytes([63, 0, 191, 255])


def test_a_resized_png_gets_the_chain_of_its_new_size(tmp_path: Path) -> None:
    export_texture(TEXTURE, tmp_path / "t.png")
    Image.new("RGBA", (8, 4), (1, 2, 3, 4)).save(tmp_path / "t.png")

    texture = import_texture(tmp_path / "t.png")

    assert (texture.width, texture.height) == (8, 4)
    assert [len(level) for level in texture.levels] == [128, 32, 8, 4]


def test_an_unknown_version_in_the_settings_is_refused(tmp_path: Path) -> None:
    export_texture(TEXTURE, tmp_path / "t.png")
    (tmp_path / "t.json").write_text('{"version": 6, "mipmaps": true}')

    with pytest.raises(ValueError, match=r"t\.json: TXTR version 6"):
        import_texture(tmp_path / "t.png")


def patched(offset: int, value: bytes) -> bytes:
    data = bytearray(encode_texture(TEXTURE))
    data[offset : offset + len(value)] = value
    return bytes(data)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (patched(0, b"RXTT"), "Not a TXTR texture"),
        (patched(4, bytes([0, 0, 0, 6])), "TXTR version 6 is not supported"),
        (patched(0x10, bytes([0, 5])), "Pixel format 5 is not supported"),
        (patched(0x26, bytes([3])), "A 2x2 texture cannot have 3 levels"),
        (
            encode_texture(Texture(7, 3, 2, (bytes(24), bytes(4)))),
            "Mipmaps of a 3x2 texture are not supported",
        ),
        (patched(0x80, bytes([0, 0, 0, 12])), "Level 0 has 12 bytes for 2x2 texels"),
        (patched(0x13, bytes([1])), "cannot keep, at offset 0x13"),
        (patched(0x9F, bytes([1])), "cannot keep, at offset 0x9f"),
        (encode_texture(TEXTURE) + bytes(32), "cannot keep, at offset 0xc0"),
    ],
)
def test_textures_this_tool_cannot_rebuild_are_refused(data: bytes, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        decode_texture(data)
