"""The pictures of the MSX games and their PNG form.

An indexed image is a little-endian u32 width and height, then one palette index
per pixel, row by row. Images carry no palette: the game decides which colours
the 256 indices show, and index 0 is never drawn. A screen is 512x424 pixels of
blue, green and red bytes, followed by two zero bytes.

Rectangles of sprite sheets are tables of 6-byte records: a sheet, the record's
number, then x, y, width and height.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import batched
from pathlib import Path

from PIL import Image

from mgtools.binary import BinaryReader, BinaryWriter
from mgtools.errors import FormatError
from mgtools.fileio import is_index, read_image, write_png
from mgtools.msx.palette import MAX_COLOURS, Colour, colour_name

type Clut = Sequence[Colour | None]
"""The colour of each palette index while an image is on screen, None if unloaded."""

SCREEN_SIZE = (512, 424)
_SCREEN_END = b"\0\0"
_RECTANGLE_FIELDS = ("x", "y", "w", "h")


@dataclass(frozen=True, slots=True)
class IndexedImage:
    """An image of one palette index per pixel, row by row."""

    width: int
    height: int
    pixels: bytes


def decode_image(data: bytes) -> IndexedImage:
    """Decode an indexed image, refusing one whose pixels do not fill its size.

    Args:
        data: The bytes of the image.
    """
    reader = BinaryReader(data)
    width, height = reader.u32(), reader.u32()
    if width * height != reader.remaining:
        msg = f"A {width}x{height} image has {width * height} pixels, not {reader.remaining}"
        raise FormatError(msg)
    return IndexedImage(width, height, reader.read(reader.remaining))


def encode_image(image: IndexedImage) -> bytes:
    """Return the bytes of an indexed image.

    Args:
        image: The image to encode.
    """
    writer = BinaryWriter()
    writer.u32(image.width)
    writer.u32(image.height)
    writer.write(image.pixels)
    return writer.getvalue()


def export_image(image: IndexedImage, clut: Clut, path: Path) -> None:
    """Save an image as an indexed PNG whose index 0 is transparent.

    Args:
        image: The image to save.
        clut: The colours the game shows the image with.
        path: The PNG to write.
    """
    png = Image.frombytes("P", (image.width, image.height), image.pixels)
    png.putpalette(bytes(channel for colour in _png_palette(clut) for channel in colour))
    png.info["transparency"] = 0
    write_png(path, png)


def colour_choices(image: IndexedImage, clut: Clut) -> dict[Colour, int]:
    """Return the indices RGB copies need for colours not drawn by their first index.

    Args:
        image: The image whose drawn indices to check.
        clut: The colours the game shows the image with.
    """
    palette = _png_palette(clut)
    first = _first_indices(palette)
    # Index 0 is transparent in the PNG, so alpha alone brings it back.
    drawn = Counter(image.pixels.translate(None, b"\0"))
    choices: dict[Colour, int] = {}
    for index, _ in drawn.most_common():
        choices.setdefault(palette[index], index)
    return {colour: index for colour, index in choices.items() if first[colour] != index}


def import_image(path: Path, clut: Clut, choices: Mapping[Colour, int]) -> IndexedImage:
    """Read an image from a PNG, by its indices if it shows them as exported.

    Args:
        path: The PNG to read.
        clut: The colours the game shows the image with.
        choices: The index to give each colour that its first index does not draw.
    """
    palette = _png_palette(clut)
    png = read_image(path)
    if png.mode == "P" and _keeps_palette(png, palette):
        return IndexedImage(png.width, png.height, png.tobytes())
    rgba = png.convert("RGBA")
    indices = _first_indices(palette)
    indices |= {colour: i for colour, i in choices.items() if palette[i] == colour}
    lookup = {(*colour, 255): index for colour, index in indices.items()}
    pixels = bytearray()
    for pixel in batched(rgba.tobytes(), 4, strict=True):
        index = 0 if pixel[3] == 0 else lookup.get(pixel)
        if index is None:
            x, y = len(pixels) % rgba.width, len(pixels) // rgba.width
            shown = colour_name(pixel[:3]) + ("" if pixel[3] == 255 else f" at alpha {pixel[3]}")
            msg = f"{path}: the pixel at ({x}, {y}) is {shown}, which no palette index shows"
            raise ValueError(msg)
        pixels.append(index)
    return IndexedImage(rgba.width, rgba.height, bytes(pixels))


def export_screen(data: bytes, path: Path) -> None:
    """Save a screen as an RGB PNG.

    Args:
        data: The bytes of the screen.
        path: The PNG to write.
    """
    width, height = SCREEN_SIZE
    pixels, end = data[: -len(_SCREEN_END)], data[-len(_SCREEN_END) :]
    if len(pixels) != width * height * 3 or end != _SCREEN_END:
        msg = f"A screen is {width}x{height} pixels of 3 bytes, then 2 zero bytes"
        raise FormatError(msg)
    write_png(path, Image.frombytes("RGB", SCREEN_SIZE, pixels, "raw", "BGR"))


def import_screen(path: Path) -> bytes:
    """Return the bytes of a screen read from a PNG of the screen's size.

    Args:
        path: The PNG to read.
    """
    png = read_image(path, SCREEN_SIZE)
    return png.convert("RGB").tobytes("raw", "BGR") + _SCREEN_END


def decode_rectangles(data: bytes, field: str, sheets: range) -> list[dict[str, int]] | None:
    """Return the rectangles of a table, naming their sheet field, if it is one.

    Args:
        data: The bytes that may be a table of rectangles.
        field: The key that gives the sheet of each rectangle.
        sheets: The sheet numbers the first byte of each record indexes.
    """
    if len(data) % 6:
        return None
    records = list(batched(data, 6, strict=True))
    if [record[1] for record in records] != list(range(len(records))) or any(
        record[0] >= len(sheets) for record in records
    ):
        return None
    return [
        {field: sheets[record[0]]} | dict(zip(_RECTANGLE_FIELDS, record[2:], strict=True))
        for record in records
    ]


def encode_rectangles(rectangles: object, field: str, sheets: range) -> bytes:
    """Build a table from rectangles as decode_rectangles gives them.

    Args:
        rectangles: The rectangles, as read from JSON.
        field: The key that gives the sheet of each rectangle.
        sheets: The sheet numbers the first byte of each record indexes.
    """
    if not isinstance(rectangles, list):
        msg = "Rectangles must be a list"
        raise ValueError(msg)
    keys = (field, *_RECTANGLE_FIELDS)
    data = bytearray()
    for number, rectangle in enumerate(rectangles):
        if not isinstance(rectangle, dict) or rectangle.keys() != set(keys):
            msg = f"Rectangle {number} must have exactly the keys {', '.join(keys)}"
            raise ValueError(msg)
        sheet, *box = (rectangle[key] for key in keys)
        if not (
            is_index(sheet - sheets.start, len(sheets))
            and all(is_index(value, 0x100) for value in box)
        ):
            msg = (
                f"Rectangle {number} needs {field} from {sheets.start} to "
                f"{sheets.stop - 1} and x, y, w and h from 0 to 255"
            )
            raise ValueError(msg)
        data += bytes((sheet - sheets.start, number, *box))
    return bytes(data)


def _keeps_palette(png: Image.Image, palette: Sequence[Colour]) -> bool:
    """Tell whether each index a PNG draws shows its colour, which some editors move."""
    shown = list(batched(png.getpalette() or [], 3, strict=True))
    drawn = set(png.tobytes()) - {0}
    return all(index < len(shown) and shown[index] == palette[index] for index in drawn)


def _first_indices(palette: Sequence[Colour]) -> dict[Colour, int]:
    """Return the lowest index that shows each colour of a palette."""
    return {colour: index for index, colour in reversed(list(enumerate(palette)))}


def _png_palette(clut: Clut) -> list[Colour]:
    """Return the 256 colours of a PNG, an unused one for each index the clut lacks."""
    colours = list(clut[:MAX_COLOURS]) + [None] * (MAX_COLOURS - len(clut))
    taken = {colour for colour in colours if colour is not None}
    return [
        colour if colour is not None else _filler(index, taken)
        for index, colour in enumerate(colours)
    ]


def _filler(index: int, taken: set[Colour]) -> Colour:
    """Return a colour no other index shows, for an index the clut lacks."""
    # Blue depends on the index alone, so the filler of an index stays the same
    # when colours are added to other indices.
    candidates = ((0xFF, green, 0xFF - index) for green in range(256))
    return next(colour for colour in candidates if colour not in taken)
