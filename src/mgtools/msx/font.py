"""The fonts of the MSX games.

The font section holds five pages. Pages 0 to 3 are proportional fonts 24, 12,
18 and 24 pixels high. Each starts with a u32 LE slot for every code from 0x1E
to 0xFF: the offset of the glyph's data in bits 0-19, its width minus 1 in bits
20-25 and a page constant in bits 26-31, or 0xFFF0 in the high half for a code
without a glyph. Slots 0x1E and 0x1F are zero on legacy pages, which are padded
to 20480 bytes, and hold the header of sized pages. The glyphs follow in code
order, 2 bits per pixel, each in ceil(width * height / 4) bytes; floor-packed
pages round down instead, and the engine draws the last two pixels of such a
glyph from the next one. Page 4 maps each double-byte code to one of its 24 by
24 pixel glyphs; every code it does not map draws glyph 0.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil

from mgtools.binary import BinaryReader, BinaryWriter, ByteOrder, packer
from mgtools.errors import FormatError

HEIGHTS = (24, 12, 18, 24)
"""The height of the glyphs of each proportional page."""
CODES = range(0x20, 0x100)
"""The codes a proportional page can give a glyph."""
DOUBLE_BYTE_SIZE = 24
"""The width and height of the glyphs of page 4."""

_FIRST_SLOT = 0x1E
_TABLE_SIZE = (0x100 - _FIRST_SLOT) * 4
_EMPTY = 0xFFF0
_LEGACY_SIZE = 20480
_DOUBLE_BYTE_GLYPH = DOUBLE_BYTE_SIZE * DOUBLE_BYTE_SIZE // 4
_DOUBLE_BYTE_MAP = packer(ByteOrder.BIG, "32768H")


@dataclass(frozen=True, slots=True)
class Glyph:
    """A glyph of a proportional page, its data as the page stores it."""

    width: int
    data: bytes


@dataclass(frozen=True, slots=True)
class Page:
    """A proportional page: its glyphs by code, codes without one left out."""

    glyphs: dict[int, Glyph]
    floor_packed: bool = False
    v: int | None = None
    """The constant of a sized page, None for a legacy page."""


@dataclass(frozen=True, slots=True)
class DoubleByteGlyph:
    """A glyph of page 4 and the double-byte code it is mapped to, if any."""

    code: int | None
    data: bytes


@dataclass(frozen=True, slots=True)
class Font:
    """A font section: the proportional pages 0 to 3 and the glyphs of page 4."""

    pages: tuple[Page, ...]
    double_byte: tuple[DoubleByteGlyph, ...]


def decode_font(pages: Sequence[bytes]) -> Font:
    """Decode the five pages of a font section.

    Args:
        pages: The data of each page.
    """
    if len(pages) != 5:
        msg = f"A font has 5 pages, not {len(pages)}"
        raise FormatError(msg)
    return Font(
        tuple(_decode_page(i, data) for i, data in enumerate(pages[:4])),
        _decode_double_byte(pages[4]),
    )


def encode_font(font: Font) -> list[bytes]:
    """Return the data of the five pages of a font section.

    Args:
        font: The font to encode.
    """
    return [
        *(_encode_page(i, page) for i, page in enumerate(font.pages)),
        _encode_double_byte(font.double_byte),
    ]


def _decode_page(index: int, data: bytes) -> Page:
    reader = BinaryReader(data)
    head, total, *words = (word for (word,) in reader.iter_unpack("I", 0x100 - _FIRST_SLOT))
    if head == total == 0:
        v, end = None, None
        if len(data) != _LEGACY_SIZE:
            msg = f"Font page {index} takes {len(data)} bytes, not {_LEGACY_SIZE}"
            raise FormatError(msg)
    elif head & 0xFF_FFFF == _TABLE_SIZE and total == len(data):
        v, end = head >> 24, len(data) - _TABLE_SIZE
    else:
        msg = f"Font page {index} has the unknown header {head:08X} {total:08X}"
        raise FormatError(msg)
    offsets = [word & (0xFFFF if word >> 16 == _EMPTY else 0xF_FFFF) for word in words]
    glyphs: dict[int, Glyph] = {}
    packings: set[bool] = set()
    position = 0
    for code, word, offset, following in zip(
        CODES, words, offsets, [*offsets[1:], end], strict=True
    ):
        if offset != position:
            msg = f"Font page {index} puts {code:02X} at {offset}, not at {position}"
            raise FormatError(msg)
        if word >> 16 == _EMPTY:
            continue
        width = (word >> 20 & 0x3F) + 1
        if word >> 26 != (v or 0) >> 2:
            msg = f"Font page {index} gives {code:02X} the unknown bits {word >> 26}"
            raise FormatError(msg)
        pixels = width * HEIGHTS[index]
        size = ceil(pixels / 4) if following is None else following - offset
        if size not in (pixels // 4, ceil(pixels / 4)):
            msg = f"Font page {index} gives {code:02X} {size} bytes for {pixels} pixels"
            raise FormatError(msg)
        if pixels % 4:
            packings.add(size == pixels // 4)
        glyphs[code] = Glyph(width, reader.read(size))
        position += size
    if len(packings) > 1:
        msg = f"Font page {index} packs some glyphs to floor and others to ceiling"
        raise FormatError(msg)
    rest = reader.read(reader.remaining)
    # Only legacy pages are padded, with zeros.
    if any(rest) or (rest and v is not None):
        msg = f"Font page {index} has data after its glyphs"
        raise FormatError(msg)
    return Page(glyphs, packings == {True}, v)


def _encode_page(index: int, page: Page) -> bytes:
    stream = b"".join(page.glyphs[code].data for code in sorted(page.glyphs))
    # Sized pages give their size in 16 bits, as do the empty slots their offset.
    room = (0xFFFF if page.v is not None else _LEGACY_SIZE) - _TABLE_SIZE
    if len(stream) > room:
        msg = f"The glyphs of font page {index} take {len(stream)} bytes of {room}"
        raise ValueError(msg)
    writer = BinaryWriter()
    if page.v is None:
        writer.pack("II", 0, 0)
    else:
        writer.pack("II", page.v << 24 | _TABLE_SIZE, _TABLE_SIZE + len(stream))
    position = 0
    for code in CODES:
        if glyph := page.glyphs.get(code):
            writer.u32(position | (glyph.width - 1) << 20 | (page.v or 0) >> 2 << 26)
            position += len(glyph.data)
        else:
            writer.u32(_EMPTY << 16 | position)
    writer.write(stream)
    if page.v is None:
        writer.write(bytes(_LEGACY_SIZE - len(writer)))
    return writer.getvalue()


def _decode_double_byte(data: bytes) -> tuple[DoubleByteGlyph, ...]:
    reader = BinaryReader(data, ByteOrder.BIG)
    if (header := reader.unpack("HH")) != (0, _DOUBLE_BYTE_GLYPH):
        msg = f"Font page 4 has the unknown header {header}"
        raise FormatError(msg)
    indices = _DOUBLE_BYTE_MAP.unpack(reader.read(_DOUBLE_BYTE_MAP.size))
    count, rest = divmod(reader.remaining, _DOUBLE_BYTE_GLYPH)
    if rest:
        msg = f"Font page 4 ends with {rest} bytes that are no glyph"
        raise FormatError(msg)
    codes: list[int | None] = [None] * count
    for code, index in enumerate(indices, 0x8000):
        if index and (index >= count or codes[index] is not None):
            msg = f"Font page 4 maps {code:04X} to glyph {index}, which it cannot"
            raise FormatError(msg)
        if index:
            codes[index] = code
    return tuple(DoubleByteGlyph(code, reader.read(_DOUBLE_BYTE_GLYPH)) for code in codes)


def _encode_double_byte(glyphs: Sequence[DoubleByteGlyph]) -> bytes:
    indices = [0] * 0x8000
    for index, glyph in enumerate(glyphs):
        if glyph.code is not None:
            indices[glyph.code - 0x8000] = index
    header = packer(ByteOrder.BIG, "HH").pack(0, _DOUBLE_BYTE_GLYPH)
    return b"".join((header, _DOUBLE_BYTE_MAP.pack(*indices), *(g.data for g in glyphs)))
