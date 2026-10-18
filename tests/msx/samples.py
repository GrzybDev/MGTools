"""Small invented fonts of the MSX games."""

from mgtools.bitmap import pack_2bpp
from mgtools.msx.font import DoubleByteGlyph, Font, Glyph, Page


def pixels(count: int, seed: int = 0) -> bytes:
    """Return a pattern of 2-bit pixels, one value from 0 to 3 per byte.

    Args:
        count: The number of pixels.
        seed: The offset of the pattern's values, to make glyphs differ.
    """
    return bytes((seed + i * 7 // 3) % 4 for i in range(count))


def glyph(width: int, height: int, seed: int = 0, *, floor: bool = False) -> Glyph:
    """Return a proportional glyph drawn with a pattern of pixels.

    Args:
        width: The glyph's width in pixels.
        height: The height of the glyphs of its page.
        seed: The offset of the pattern's values.
        floor: Whether its page is floor-packed, which drops a partial last byte.
    """
    data = pack_2bpp(pixels(width * height, seed))
    return Glyph(width, data[: width * height // 4] if floor else data)


def double_byte(code: int | None, seed: int = 0) -> DoubleByteGlyph:
    """Return a glyph of page 4 drawn with a pattern of pixels.

    Args:
        code: The double-byte code mapped to the glyph, or None for an unmapped one.
        seed: The offset of the pattern's values.
    """
    return DoubleByteGlyph(code, pack_2bpp(pixels(24 * 24, seed)))


FONT = Font(
    pages=(
        Page({0x20: glyph(4, 24), 0x41: glyph(7, 24, 1), 0xA7: glyph(5, 24, 2)}),
        Page({0x20: glyph(3, 12), 0x42: glyph(5, 12, 1), 0xFF: glyph(2, 12, 3)}, v=12),
        Page(
            {
                0x41: glyph(3, 18, floor=True),
                0x43: glyph(2, 18, 1, floor=True),
                0x45: glyph(5, 18, 2, floor=True),
            },
            floor_packed=True,
        ),
        Page({}),
    ),
    double_byte=(double_byte(None), double_byte(0x82A0, 1), double_byte(0x8341, 2)),
)
"""A font with every kind of page: legacy, sized, floor-packed and empty."""

_PADDED = glyph(3, 18, 3)
PADDED_FONT = Font(
    pages=(
        *FONT.pages[:2],
        Page(
            {0x41: Glyph(3, _PADDED.data[:-1] + bytes((_PADDED.data[-1] | 0b1010,)))},
            v=16,
        ),
        FONT.pages[3],
    ),
    double_byte=(),
)
"""A font whose ceiling-packed page 2 keeps bits after a glyph's last pixel."""
