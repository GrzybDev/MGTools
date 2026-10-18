from pathlib import Path

import pytest
from PIL import Image

from mgtools.errors import FormatError
from mgtools.msx.images import (
    SCREEN_SIZE,
    Clut,
    IndexedImage,
    colour_choices,
    decode_image,
    decode_rectangles,
    encode_image,
    encode_rectangles,
    export_image,
    export_screen,
    import_image,
    import_screen,
)

MAGENTA, BLACK, ORANGE = (255, 0, 255), (0, 0, 0), (200, 100, 50)
CLUT: Clut = [MAGENTA, BLACK, ORANGE, None, BLACK]
"""Index 3 has no colour; 1 and 4 show the same one."""


def flatten(path: Path) -> None:
    with Image.open(path) as png:
        rgba = png.convert("RGBA")
    rgba.save(path)


def test_images_are_width_and_height_then_one_index_per_pixel() -> None:
    data = bytes.fromhex("03000000 01000000 000102")

    assert decode_image(data) == IndexedImage(3, 1, b"\0\1\2")
    assert encode_image(IndexedImage(3, 1, b"\0\1\2")) == data


def test_an_image_with_more_pixels_than_its_size_is_refused() -> None:
    with pytest.raises(FormatError, match="A 2x1 image has 2 pixels, not 3"):
        decode_image(bytes.fromhex("02000000 01000000 000102"))


def test_images_become_indexed_pngs_with_their_colours_and_0_transparent(
    tmp_path: Path,
) -> None:
    export_image(IndexedImage(2, 1, b"\0\2"), CLUT, tmp_path / "image.png")

    with Image.open(tmp_path / "image.png") as png:
        assert png.mode == "P"
        assert png.info["transparency"] == 0
        assert png.convert("RGBA").tobytes() == bytes((*MAGENTA, 0, *ORANGE, 255))


def test_indices_without_colours_get_colours_no_other_index_shows(
    tmp_path: Path,
) -> None:
    export_image(IndexedImage(1, 1, b"\0"), CLUT, tmp_path / "image.png")

    with Image.open(tmp_path / "image.png") as png:
        palette = png.getpalette()
    assert palette is not None
    colours = [tuple(palette[i : i + 3]) for i in range(0, 768, 3)]
    fillers = colours[3:4] + colours[5:]
    assert len(set(fillers)) == len(fillers) == 252
    assert not set(fillers) & {MAGENTA, BLACK, ORANGE}


def test_indexed_pngs_that_keep_their_palette_give_their_indices(
    tmp_path: Path,
) -> None:
    image = IndexedImage(4, 1, bytes([0, 1, 4, 250]))
    export_image(image, CLUT, tmp_path / "image.png")

    assert import_image(tmp_path / "image.png", CLUT, {}) == image


def test_indexed_pngs_whose_palette_an_editor_sorted_are_read_by_colour(
    tmp_path: Path,
) -> None:
    png = Image.new("P", (3, 1))
    png.putpalette(bytes((*ORANGE, *MAGENTA, *BLACK)))
    png.putdata([1, 0, 2])
    png.save(tmp_path / "image.png", transparency=1)

    image = import_image(tmp_path / "image.png", CLUT, {})

    assert image == IndexedImage(3, 1, bytes([0, 2, 1]))


def test_rgba_copies_find_their_indices_again(tmp_path: Path) -> None:
    image = IndexedImage(3, 2, bytes([0, 1, 2, 3, 250, 0]))
    export_image(image, CLUT, tmp_path / "image.png")
    flatten(tmp_path / "image.png")

    assert import_image(tmp_path / "image.png", CLUT, {}) == image


def test_a_colour_several_indices_show_is_the_first_unless_chosen(
    tmp_path: Path,
) -> None:
    image = IndexedImage(2, 1, bytes([4, 2]))
    export_image(image, CLUT, tmp_path / "image.png")
    flatten(tmp_path / "image.png")

    choices = colour_choices(image, CLUT)

    assert choices == {BLACK: 4}
    assert import_image(tmp_path / "image.png", CLUT, choices) == image
    assert import_image(tmp_path / "image.png", CLUT, {}).pixels == bytes([1, 2])


def test_indices_without_colours_keep_theirs_when_others_gain_colours(
    tmp_path: Path,
) -> None:
    image = IndexedImage(1, 1, bytes([250]))
    export_image(image, CLUT, tmp_path / "image.png")
    flatten(tmp_path / "image.png")

    edited = [*CLUT[:3], (1, 2, 3), *CLUT[4:]]

    assert import_image(tmp_path / "image.png", edited, {}) == image


def test_choices_take_the_index_an_image_draws_most() -> None:
    clut: Clut = [MAGENTA, BLACK, ORANGE, BLACK]

    assert colour_choices(IndexedImage(3, 1, bytes([1, 3, 3])), clut) == {BLACK: 3}
    assert colour_choices(IndexedImage(3, 1, bytes([1, 1, 3])), clut) == {}


def test_choices_leave_out_index_0_which_transparency_brings_back() -> None:
    clut: Clut = [BLACK, ORANGE, BLACK]

    assert colour_choices(IndexedImage(4, 1, bytes([0, 0, 0, 2])), clut) == {BLACK: 2}


def test_choices_whose_index_shows_another_colour_are_ignored(tmp_path: Path) -> None:
    export_image(IndexedImage(1, 1, b"\1"), CLUT, tmp_path / "image.png")
    flatten(tmp_path / "image.png")

    assert import_image(tmp_path / "image.png", CLUT, {BLACK: 2}).pixels == b"\1"


@pytest.mark.parametrize(
    ("pixel", "shown"),
    [((1, 2, 3, 255), "#010203"), ((*ORANGE, 128), "#c86432 at alpha 128")],
)
def test_colours_no_index_shows_are_reported_with_their_place(
    tmp_path: Path, pixel: tuple[int, int, int, int], shown: str
) -> None:
    png = Image.new("RGBA", (2, 2), (*ORANGE, 255))
    png.putpixel((1, 1), pixel)
    png.save(tmp_path / "image.png")

    with pytest.raises(ValueError, match=rf"\(1, 1\) is {shown}, which no palette"):
        import_image(tmp_path / "image.png", CLUT, {})


def test_screens_turn_blue_green_red_into_rgb_pngs_and_back(tmp_path: Path) -> None:
    pixels = bytearray(SCREEN_SIZE[0] * SCREEN_SIZE[1] * 3)
    pixels[:3] = b"\x01\x02\x03"
    data = bytes(pixels) + b"\0\0"

    export_screen(data, tmp_path / "screen.png")

    with Image.open(tmp_path / "screen.png") as png:
        assert png.mode == "RGB"
        assert png.getpixel((0, 0)) == (3, 2, 1)
    assert import_screen(tmp_path / "screen.png") == data


@pytest.mark.parametrize("end", [b"\0\1", b"\0", b"\0\0\0"])
def test_screens_end_in_two_zero_bytes(tmp_path: Path, end: bytes) -> None:
    data = bytes(SCREEN_SIZE[0] * SCREEN_SIZE[1] * 3) + end

    with pytest.raises(FormatError, match="pixels of 3 bytes, then 2 zero bytes"):
        export_screen(data, tmp_path / "screen.png")


def test_screens_keep_their_size(tmp_path: Path) -> None:
    Image.new("RGB", (512, 423)).save(tmp_path / "screen.png")

    with pytest.raises(ValueError, match="is 512x423 pixels, not 512x424"):
        import_screen(tmp_path / "screen.png")


def test_rectangle_tables_name_their_sheet_and_number_their_records() -> None:
    data = bytes([0, 0, 1, 2, 3, 4, 2, 1, 5, 6, 7, 8])
    rectangles = [
        {"sheet": 41, "x": 1, "y": 2, "w": 3, "h": 4},
        {"sheet": 43, "x": 5, "y": 6, "w": 7, "h": 8},
    ]

    assert decode_rectangles(data, "sheet", range(41, 71)) == rectangles
    assert encode_rectangles(rectangles, "sheet", range(41, 71)) == data


@pytest.mark.parametrize("data", [bytes([0, 1, 0, 0, 0, 0]), bytes(7), bytes([30, 0, 0, 0, 0, 0])])
def test_tables_not_numbered_from_0_or_naming_other_sheets_are_not_rectangles(
    data: bytes,
) -> None:
    assert decode_rectangles(data, "sheet", range(41, 71)) is None


@pytest.mark.parametrize(
    ("rectangles", "message"),
    [
        ({"slot": 0}, "must be a list"),
        ([{"slot": 0, "x": 0, "y": 0, "w": 0}], "Rectangle 0 must have exactly"),
        ([{"slot": 3, "x": 256, "y": 0, "w": 0, "h": 0}], "needs slot from 3 to 83"),
        ([{"slot": 84, "x": 0, "y": 0, "w": 0, "h": 0}], "needs slot from 3 to 83"),
        ([{"slot": 2, "x": 0, "y": 0, "w": 0, "h": 0}], "needs slot from 3 to 83"),
        ([{"slot": 3, "x": "1", "y": 0, "w": 0, "h": 0}], "and x, y, w and h"),
    ],
)
def test_edited_rectangles_are_checked(rectangles: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        encode_rectangles(rectangles, "slot", range(3, 84))
