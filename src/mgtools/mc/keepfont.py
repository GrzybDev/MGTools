"""keepfont: the 2-bit font of keepfont*.raw.

Little-endian: the end of the glyph table (u16), a u16 of unknown meaning and the
end of the Latin glyphs (u32); then the table, a u16 offset from its end and a
u16 info per Latin glyph, for the byte codes 0x20 to 0xFF in the Mac OS Roman
layout. Bits 4 to 9 of the info hold the width minus 1 and the others are flags
(0x800 marks descenders). A Latin glyph is 24 rows of its width in 2-bit pixels,
packed as one stream. Kana glyphs of 24 by 24 pixels fill the rest of the file,
which zeros pad to a multiple of 16 bytes.
"""

from dataclasses import dataclass, replace
from itertools import batched
from pathlib import Path
from typing import Any

from mgtools.binary import BinaryReader, BinaryWriter
from mgtools.bitmap import grey_image, grey_pixels, pack_2bpp, unpack_2bpp
from mgtools.errors import FormatError, located
from mgtools.fileio import (
    convert_json,
    is_index,
    read_image,
    write_json,
    write_png,
)

_HEIGHT = 24
_FIRST_CODE = 0x20
_CODES = 0x100 - _FIRST_CODE
_WIDTH_BITS = 0x3F0
_KANA_PIXELS = _HEIGHT * _HEIGHT
_DOCUMENT = "keepfont.json"
_KANA = "kana.png"


@dataclass(frozen=True, slots=True)
class LatinGlyph:
    """The glyph of a byte code from 0x20 up: 24 pixels high and from 1 to 64 wide."""

    width: int
    flags: int
    """The bits of the glyph's info besides its width."""
    pixels: bytes
    """24 rows of width values from 0 to 3."""
    unused: bytes = b""
    """Bytes stored after the glyph that no table entry points at."""


@dataclass(frozen=True, slots=True)
class Keepfont:
    """The font of a keepfont*.raw file: its Latin glyphs, then its kana."""

    header: int
    """The header word of unknown meaning."""
    latin: tuple[LatinGlyph, ...]
    kana: tuple[bytes, ...]
    """24 rows of 24 values from 0 to 3 per glyph."""


def decode_keepfont(data: bytes) -> Keepfont:
    """Read a keepfont, keeping the bytes between glyphs that the table skips.

    Args:
        data: The contents of a keepfont*.raw file.
    """
    reader = BinaryReader(data)
    table_end, header, latin_end = reader.unpack("HHI")
    count, rest = divmod(table_end - reader.position, 4)
    if not 1 <= count <= _CODES or rest:
        msg = f"The glyph table cannot end at offset {table_end}"
        raise FormatError(msg)
    latin: list[LatinGlyph] = []
    position = table_end
    entries = reader.iter_unpack("HH", count)
    for code, (offset, info) in enumerate(entries, _FIRST_CODE):
        start = table_end + offset
        if start < position or (start > position and not latin):
            msg = f"The glyph of {code:#04x} starts at {start}, not at {position}"
            raise FormatError(msg)
        if start > position:
            latin[-1] = replace(latin[-1], unused=data[position:start])
        width = ((info & _WIDTH_BITS) >> 4) + 1
        position = start + _HEIGHT * width // 4
        pixels = unpack_2bpp(data[start:position], _HEIGHT * width)
        latin.append(LatinGlyph(width, info & ~_WIDTH_BITS, pixels))
    if position > latin_end:
        msg = f"The Latin glyphs end at {position}, after {latin_end}"
        raise FormatError(msg)
    latin[-1] = replace(latin[-1], unused=data[position:latin_end])
    size = _KANA_PIXELS // 4
    end = latin_end + (len(data) - latin_end) // size * size
    if data[end:] != bytes(-end % 16):
        msg = f"The file should end with {-end % 16} zeros after the kana at {end}"
        raise FormatError(msg)
    kana = unpack_2bpp(data[latin_end:end], (end - latin_end) * 4)
    return Keepfont(header, tuple(latin), _split_kana(kana))


def encode_keepfont(font: Keepfont) -> bytes:
    """Return the keepfont*.raw file of a font, with the table that follows from its glyphs.

    Args:
        font: The font to write.
    """
    if len(font.latin) > _CODES:
        msg = f"The Latin glyphs are for the {_CODES} byte codes 0x20 to 0xff only"
        raise ValueError(msg)
    table, glyphs = BinaryWriter(), bytearray()
    for code, glyph in enumerate(font.latin, _FIRST_CODE):
        if not 1 <= glyph.width <= 64 or len(glyph.pixels) != _HEIGHT * glyph.width:
            msg = f"The glyph of {code:#04x} must be 1 to 64 wide and {_HEIGHT} high"
            raise ValueError(msg)
        if glyph.flags & _WIDTH_BITS:
            msg = f"The flags of {code:#04x} overlap the width bits {_WIDTH_BITS:#x}"
            raise ValueError(msg)
        if len(glyphs) > 0xFFFF:
            msg = (
                f"The glyph of {code:#04x} starts past the 64 KiB the table's offsets "
                "reach: make some glyphs narrower"
            )
            raise ValueError(msg)
        table.pack("HH", len(glyphs), glyph.flags | (glyph.width - 1) << 4)
        glyphs += pack_2bpp(glyph.pixels) + glyph.unused
    if any(len(pixels) != _KANA_PIXELS for pixels in font.kana):
        msg = f"Every kana glyph holds {_KANA_PIXELS} pixels"
        raise ValueError(msg)
    table_end = 8 + len(table)
    writer = BinaryWriter()
    writer.pack("HHI", table_end, font.header, table_end + len(glyphs))
    writer.write(table.getvalue())
    writer.write(glyphs)
    writer.write(pack_2bpp(b"".join(font.kana)))
    writer.write(bytes(-len(writer) % 16))
    return writer.getvalue()


def export_keepfont(font: Keepfont, directory: Path) -> None:
    """Write keepfont.json, a PNG per Latin glyph and the kana as one column.

    Args:
        font: The font to write.
        directory: The folder to write the files to.
    """
    rows = []
    for code, glyph in enumerate(font.latin, _FIRST_CODE):
        image = grey_image(glyph.pixels, (glyph.width, _HEIGHT))
        write_png(directory / _latin(code), image)
        row: dict[str, Any] = {"code": f"{code:#04x}", "flags": glyph.flags}
        if glyph.unused:
            row["unused"] = glyph.unused.hex()
        rows.append(row)
    kana = grey_image(b"".join(font.kana), (_HEIGHT, _HEIGHT * len(font.kana)))
    write_png(directory / _KANA, kana)
    write_json(directory / _DOCUMENT, {"header": font.header, "latin": rows})


def import_keepfont(directory: Path) -> Keepfont:
    """Read a font written by export_keepfont; the PNGs give the glyph widths.

    Args:
        directory: The folder export_keepfont wrote.
    """
    header, rows = convert_json(directory / _DOCUMENT, _document)
    latin = []
    for code, (flags, unused) in enumerate(rows, _FIRST_CODE):
        image_path = directory / _latin(code)
        width, pixels = _load(image_path)
        if len(pixels) != _HEIGHT * width:
            msg = f"{image_path} must be {_HEIGHT} pixels high"
            raise ValueError(msg)
        latin.append(LatinGlyph(width, flags, pixels, unused))
    width, kana = _load(directory / _KANA)
    if width != _HEIGHT or len(kana) % _KANA_PIXELS:
        msg = f"{directory / _KANA} must be a column of {_HEIGHT}-pixel squares"
        raise ValueError(msg)
    return Keepfont(header, tuple(latin), _split_kana(kana))


def _document(document: Any) -> tuple[int, list[tuple[int, bytes]]]:
    """Return the header and each Latin glyph's flags and unused bytes."""
    header = document["header"]
    if not is_index(header, 0x10000):
        msg = f"The header {header!r} is not a 16-bit word"
        raise ValueError(msg)
    rows = []
    for expected, row in enumerate(document["latin"], _FIRST_CODE):
        code, flags = int(row["code"], 16), row["flags"]
        if code != expected:
            msg = f"It lists {code:#04x} where {expected:#04x} belongs"
            raise ValueError(msg)
        if not is_index(flags, 0x10000):
            msg = f"The flags {flags!r} of {code:#04x} are not a 16-bit word"
            raise ValueError(msg)
        rows.append((flags, bytes.fromhex(row.get("unused", ""))))
    return header, rows


def _split_kana(pixels: bytes) -> tuple[bytes, ...]:
    return tuple(bytes(glyph) for glyph in batched(pixels, _KANA_PIXELS, strict=True))


def _latin(code: int) -> str:
    """Return the path of a Latin glyph's PNG, relative to the exported folder."""
    return f"latin/{code:02X}.png"


def _load(path: Path) -> tuple[int, bytes]:
    """Return the width of a PNG and its pixels as 2-bit values."""
    image = read_image(path)
    with located(path):
        return image.width, grey_pixels(image)
