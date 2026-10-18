"""Small invented fonts, text sections and resource files of the MSX games."""

import struct
from collections.abc import Iterable, Sequence

from mgtools.bitmap import pack_2bpp
from mgtools.msx.charset import EU_CHARMAP, JP_CHARMAP
from mgtools.msx.container import Container, Leaf, Node, encode_node, encode_nodes
from mgtools.msx.font import DoubleByteGlyph, Font, Glyph, Page, encode_font
from mgtools.msx.images import SCREEN_SIZE, IndexedImage, encode_image
from mgtools.msx.palette import Colour, encode_palette


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


def text_font(*, japanese: bool = False, double_bytes: Sequence[int] = (0x819A,)) -> Font:
    """Return a font with glyphs for ASCII and the charmap but Ï, Japanese if asked.

    Args:
        japanese: Whether to take the Japanese charmap and make pages 1 to 3 sized.
        double_bytes: The double-byte codes mapped to the glyphs after glyph 0.
    """
    charmap = JP_CHARMAP if japanese else EU_CHARMAP
    codes = [*range(0x20, 0x7F), *(code for code in charmap if code != 0xC7)]
    empty = Page({}, v=12 if japanese else None)
    return Font(
        pages=(Page({code: glyph(2, 24, code) for code in codes}), empty, empty, empty),
        double_byte=(double_byte(None), *map(double_byte, double_bytes)),
    )


def strings(entries: Iterable[bytes | tuple[int, bytes]]) -> bytes:
    """Return a block of strings, each with a style byte in MG1.

    Args:
        entries: The data of each string, paired with its style byte for MG1.
    """
    block = b""
    for entry in entries:
        style, data = entry if isinstance(entry, tuple) else (None, entry)
        block += b"" if style is None else bytes((style,))
        block += struct.pack(">H", len(data)) + data
    return block


MG1_WARPS = [
    (b"\x01\x00\x02\x00", b"Dock", 640, 480, 3),
    (b"\x00\x00\x00\x07", "倉庫の入口".encode("cp932"), 2048, 96, 0),
]
MG1_BLOCKS = [
    bytes(range(6)),
    bytes(range(8)),
    bytes(range(12)),
    strings([(0, b"Hello, Snake!"), (1, b"Phew, safe!")]),
    strings([(2, b"Took the\nspare key."), (26, b"The crates were stacked")]),
    strings([(4, b"Big Boss calling.\n\nKeep low.")]),
    strings([(4, b"Schneider here.")]),
    strings([]),
    strings([(4, b"Diane.")]),
    strings([(4, b"Jennifer.")]),
    bytes(range(5, 0, -1)),
    bytes(3),
    b"".join(
        params + struct.pack(">H", len(name)) + name + struct.pack(">HHB", x, y, flag)
        for params, name, x, y, flag in MG1_WARPS
    ),
    strings([(4, b"Snake, do you read me?")]),
    strings([(4, b"\x81\x63 Mission complete \x81\x9a")]),
    strings(
        [
            (0, b"GADGETS"),
            (0, b"TUNE"),
            (0, b"Mine\n" + b"It explodes. " * 20),
            (0, b"FUEL"),
            (0, b"CAF\xbd"),
        ]
    ),
    bytes(range(9)),
]
"""An MG1 text section: tables, strings with styles and the warp list."""

MG2_BLOCKS = [
    strings([b"Cigarettes\nMay harm your health."]),
    strings([b"Handgun"]),
    strings([b"\\sSnake\\r: \nSnake checking in.\\w"]),
    strings([b"Campbell\\r: \n\\2Snake!\\B14\\w", b"Campbell\\r: \nOver.\\W"]),
    *(strings([b"-"]) for _ in range(13)),
    strings([b"\n".join(b"Line %d" % n for n in range(12))]),
    strings([b"STAFF"]),
    strings([b"Push the |4 button."]),
    strings([]),
    strings([b"Warp 1"]),
    strings([b"Campbell", b"\x81\x9a" * 3]),
    strings([b"Results"]),
]
"""An MG2 text section: one list of strings for each of its 24 blocks."""

FONT_PAGES = encode_font(text_font())
SCREEN = bytes(SCREEN_SIZE[0] * SCREEN_SIZE[1] * 3) + b"\0\0"
MG1_PALETTE: list[Colour] = [(255, 0, 255), (0, 0, 0), (200, 100, 50), (0, 0, 0)]
MG1_RECTANGLES = bytes([0, 0, 1, 2, 3, 4, 1, 1, 5, 6, 7, 8])
MG2_CELLS = encode_nodes([Leaf(bytes([3, 0, 1, 2, 3, 4])), Leaf(b"")])


def image(width: int, height: int, data: bytes) -> Leaf:
    """Return the leaf of an indexed image.

    Args:
        width: The image's width in pixels.
        height: The image's height in pixels.
        data: One palette index per pixel, row by row.
    """
    return Leaf(encode_image(IndexedImage(width, height, data)))


def leaves(payloads: Iterable[bytes]) -> Container:
    """Return a container of one leaf per payload.

    Args:
        payloads: The data of each leaf.
    """
    return Container(tuple(map(Leaf, payloads)))


def mg1_file() -> bytes:
    """Return an MG1 resource file: placeholder sections and sample images, texts and font."""
    sections: list[Node] = [Container((Leaf(bytes([n])),)) for n in range(77)]
    tiles = image(2, 1, bytes([1, 2]))
    sections[0] = Container((Leaf(b"\x01\x03"), Leaf(b"\x00"), *[tiles] * 4))
    sections[20] = Container((Container((Leaf(b"map"), Leaf(b"\x00"))),))
    sections[40] = Container(
        (
            Container((Leaf(MG1_RECTANGLES), Leaf(b"animation"))),
            Container(()),
            Container((Leaf(b"8 bytes!"),)),
        )
    )
    sections[41] = Container((image(2, 2, bytes([0, 3, 2, 3])), Leaf(b"")))
    sections[42:71] = [Container((Leaf(b""),))] * 29
    sections[72] = leaves(MG1_BLOCKS)
    sections[74] = leaves([encode_palette(MG1_PALETTE)])
    sections[75] = leaves(FONT_PAGES)
    sections[76] = leaves([SCREEN])
    return encode_node(Container(tuple(sections)))


def mg2_palette(number: int) -> list[Colour]:
    """Return a two-colour palette whose red is its number, to tell palettes apart.

    Args:
        number: The palette's number in its section.
    """
    return [(number, 0, 0), (number, 0, 1)]


def mg2_file(sprite_sets: dict[int, set[int]]) -> bytes:
    """Return an MG2 file of 36 one-pixel sprite sheets, loaded by the sprite sets.

    Args:
        sprite_sets: The sheets each sprite set loads, by the set's number.
    """
    sections: list[Node] = [Container((Leaf(bytes([n])),)) for n in range(49)]
    sections[0] = Container((*[Leaf(b"animation")] * 42, Leaf(MG2_CELLS)))
    table = bytearray(23 * 82)
    for number, sheets in sprite_sets.items():
        for sheet in sheets:
            table[number * 82 + sheet] = 1
    sections[1] = Container((*[Leaf(b"table")] * 6, Leaf(bytes(table))))
    sections[2] = leaves(MG2_BLOCKS)
    sections[24] = Container(tuple(image(1, 1, b"\x60") for _ in range(36)))
    sections[25] = Container((image(1, 1, b"\xc0"),))
    sections[26] = Container((image(1, 1, b"\xc1"), image(1, 1, b"\x7c")))
    sections[27:46] = [Container((image(1, 1, b"\0"),))] * 19
    sections[46] = leaves(encode_palette(mg2_palette(n)) for n in range(43))
    sections[47] = leaves([SCREEN, SCREEN])
    sections[48] = leaves(FONT_PAGES)
    return encode_node(Container(tuple(sections)))
