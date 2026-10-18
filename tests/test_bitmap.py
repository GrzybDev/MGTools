from pathlib import Path

import pytest
from PIL import Image

from mgtools.bitmap import (
    glyph_sheet,
    grey_image,
    grey_pixels,
    pack_2bpp,
    read_glyph_sheet,
    unpack_2bpp,
)
from mgtools.errors import FormatError

GREYS = [(0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255)]


def test_the_first_pixel_takes_the_highest_bits() -> None:
    assert pack_2bpp(bytes([0, 1, 2, 3, 3, 2, 1, 0])) == b"\x1b\xe4"
    assert unpack_2bpp(b"\x1b\xe4", 8) == bytes([0, 1, 2, 3, 3, 2, 1, 0])


@pytest.mark.parametrize("count", range(9))
def test_streams_of_any_length_round_trip(count: int) -> None:
    pixels = bytes(i % 4 for i in range(3, 3 + count))

    data = pack_2bpp(pixels)

    assert len(data) == (count + 3) // 4
    assert unpack_2bpp(data, count) == pixels


def test_the_unused_end_of_the_last_byte_is_zero() -> None:
    assert pack_2bpp(bytes([3, 3, 3])) == b"\xfc"


def test_only_the_pixels_asked_for_are_read() -> None:
    assert unpack_2bpp(b"\xff\xff\xff", 3) == bytes([3, 3, 3])


def test_a_stream_shorter_than_its_pixels_is_reported() -> None:
    with pytest.raises(FormatError, match="9 pixels take 3 bytes, but only 2"):
        unpack_2bpp(b"\x00\x00", 9)


def test_values_above_3_are_refused() -> None:
    with pytest.raises(ValueError, match="not 4"):
        pack_2bpp(bytes([0, 4]))


def test_images_show_the_values_as_greys_and_give_them_back() -> None:
    pixels = bytes([0, 1, 2, 3, 3, 2])

    image = grey_image(pixels, (3, 2))

    assert image.mode == "P"
    assert image.convert("RGB").tobytes() == b"".join(bytes(GREYS[v]) for v in pixels)
    assert grey_pixels(image) == pixels


@pytest.mark.parametrize("mode", ["RGB", "L"])
def test_edited_images_without_a_palette_map_greys_back_to_values(mode: str) -> None:
    image = Image.new("RGB", (4, 1))
    image.putdata([GREYS[3], GREYS[1], GREYS[0], GREYS[2]])

    assert grey_pixels(image.convert(mode)) == bytes([3, 1, 0, 2])


def test_only_fully_transparent_pixels_count_as_0() -> None:
    image = Image.new("RGBA", (2, 1))
    image.putdata([(200, 10, 10, 0), (*GREYS[2], 255)])

    assert grey_pixels(image) == bytes([0, 2])
    image.putpixel((0, 0), (*GREYS[2], 128))
    with pytest.raises(ValueError, match=r"\(0, 0\) is not one of the four greys"):
        grey_pixels(image)


def test_a_box_reads_part_of_an_image_and_errors_name_image_coordinates() -> None:
    image = Image.new("RGB", (4, 3), GREYS[0])
    image.putpixel((2, 2), GREYS[1])
    image.putpixel((3, 2), (100, 100, 100))

    assert grey_pixels(image, (1, 1, 3, 3)) == bytes([0, 0, 0, 1])
    with pytest.raises(ValueError, match=r"\(3, 2\) is not one of the four greys"):
        grey_pixels(image, (2, 1, 4, 3))


def test_indexed_images_give_their_indices_up_to_3() -> None:
    image = Image.new("P", (2, 1))
    image.putpalette(bytes(range(256)) * 3)
    image.putdata([3, 7])

    with pytest.raises(ValueError, match=r"\(1, 0\) has palette index 7"):
        grey_pixels(image)
    assert grey_pixels(image, (0, 0, 1, 1)) == bytes([3])


def test_glyph_sheets_draw_glyphs_in_rows_on_a_background_and_read_them_back(
    tmp_path: Path,
) -> None:
    glyphs = [pack_2bpp(bytes([value]) * 4) for value in (0, 1, 2)]
    path = tmp_path / "glyphs.png"

    sheet = glyph_sheet(glyphs, 2, 2, background=3)
    sheet.save(path)

    assert sheet.size == (4, 4)
    assert sheet.tobytes() == bytes([0, 0, 1, 1] * 2 + [2, 2, 3, 3] * 2)
    assert read_glyph_sheet(path, 3, 2, 2) == glyphs
