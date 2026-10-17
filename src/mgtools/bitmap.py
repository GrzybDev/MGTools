"""2-bit pixels: the packed streams of the fonts and glyphs, and their PNG form.

A stream packs four pixels per byte, the first in the two highest bits, with no
padding between rows. In PNGs the values 0 to 3 show as four levels of grey.
"""

from itertools import batched

from PIL import Image

from mgtools.errors import FormatError

_GREYS = (0, 85, 170, 255)
GREY_PALETTE = bytes(level for level in _GREYS for _ in range(3))
"""The palette of the PNGs, as Image.putpalette takes it."""

_VALUES: dict[tuple[int, ...], int] = {
    (level, level, level, 255): value for value, level in enumerate(_GREYS)
}
_FOUR_PIXELS = tuple(
    bytes((byte >> 6, byte >> 4 & 3, byte >> 2 & 3, byte & 3)) for byte in range(256)
)


def unpack_2bpp(data: bytes, count: int) -> bytes:
    """Return the first count pixels of a stream, one value from 0 to 3 per byte.

    Args:
        data: The stream, which may go on past the pixels.
        count: The number of pixels to read.
    """
    size = (count + 3) // 4
    if len(data) < size:
        msg = f"{count} pixels take {size} bytes, but only {len(data)} are left"
        raise FormatError(msg)
    return b"".join(_FOUR_PIXELS[byte] for byte in data[:size])[:count]


def pack_2bpp(pixels: bytes) -> bytes:
    """Pack values from 0 to 3 into a stream, filling its last byte with zeros.

    Args:
        pixels: One value from 0 to 3 per byte.
    """
    if max(pixels, default=0) > 3:
        msg = f"2-bit pixels take values 0 to 3, not {max(pixels)}"
        raise ValueError(msg)
    return bytes(
        a << 6 | b << 4 | c << 2 | d
        for a, b, c, d in batched(pixels + bytes(-len(pixels) % 4), 4, strict=True)
    )


def grey_image(pixels: bytes, size: tuple[int, int]) -> Image.Image:
    """Return an indexed image of values from 0 to 3, shown as greys.

    Args:
        pixels: One value from 0 to 3 per byte, row by row.
        size: The width and height of the image.
    """
    image = Image.frombytes("P", size, pixels)
    image.putpalette(GREY_PALETTE)
    return image


def grey_pixels(image: Image.Image, box: tuple[int, int, int, int] | None = None) -> bytes:
    """Return the 2-bit values of an image's pixels, from its indices or its greys.

    Args:
        image: An indexed image, or one drawn in the four greys.
        box: The left, top, right and bottom of the region to read, or None for all.
    """
    region = image.crop(box) if box else image
    indexed = region.mode == "P"
    if indexed:
        values = region.tobytes()
    else:
        values = bytes(
            0 if pixel[3] == 0 else _VALUES.get(pixel, len(_GREYS))
            for pixel in batched(region.convert("RGBA").tobytes(), 4, strict=True)
        )
    if (wrong := next((i for i, v in enumerate(values) if v > 3), None)) is not None:
        left, top = box[:2] if box else (0, 0)
        x, y = left + wrong % region.width, top + wrong // region.width
        problem = (
            f"has palette index {values[wrong]}" if indexed else "is not one of the four greys"
        )
        msg = f"The pixel at ({x}, {y}) {problem}: 2-bit pixels take values 0 to 3"
        raise ValueError(msg)
    return values
