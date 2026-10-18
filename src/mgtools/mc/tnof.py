"""TNOF fonts: the 8-bit glyphs the engine draws UTF-8 text with (MGS_Font.raw).

Little-endian: "TNOF", three words of unknown meaning, the offset of the table
(0x18) and its number of entries; the table, a code point and a record offset per
entry, sorted by code point; then a record per entry in table order: width,
height, signed bearings x and y, advance, and a coverage byte per pixel. Every
entry of a code points at the last record of that code, so the earlier records
of a repeated code are stored but never drawn.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from mgtools.binary import BinaryReader, BinaryWriter
from mgtools.errors import FormatError
from mgtools.fileio import read_image, write_json, write_png
from mgtools.mc.roundtrip import import_json

_MAGIC = b"TNOF"
_TABLE_OFFSET = 0x18
_RECORD = "BBbbB"
_CODE = re.compile(r"U\+([0-9A-Fa-f]{4,6})")
_DOCUMENT = "font.json"
_IMAGES = "glyphs"


@dataclass(frozen=True, slots=True)
class Glyph:
    """A glyph record; pixels holds a coverage value per pixel, row by row."""

    code: int
    width: int
    height: int
    bearing_x: int
    bearing_y: int
    advance: int
    pixels: bytes


@dataclass(frozen=True, slots=True)
class TnofFont:
    """A TNOF font: its header words and its glyph records in table order."""

    header: tuple[int, int, int]
    """The three words of unknown meaning after the magic."""
    glyphs: tuple[Glyph, ...]


def decode_tnof(data: bytes) -> TnofFont:
    """Read a TNOF font, refusing an entry that does not point at the last record of its code.

    Args:
        data: The contents of a TNOF file such as MGS_Font.raw.
    """
    reader = BinaryReader(data)
    if (magic := reader.read(4)) != _MAGIC:
        msg = f"Not a TNOF font: it starts with {magic!r}"
        raise FormatError(msg)
    first, second, third, table_offset, count = reader.unpack("5I")
    if table_offset != _TABLE_OFFSET:
        msg = f"The glyph table is at offset {table_offset}, not {_TABLE_OFFSET}"
        raise FormatError(msg)
    table = list(reader.iter_unpack("II", count))
    glyphs, offsets = [], []
    for code, _ in table:
        offsets.append(reader.position)
        width, height, bearing_x, bearing_y, advance = reader.unpack(_RECORD)
        pixels = reader.read(width * height)
        glyphs.append(Glyph(code, width, height, bearing_x, bearing_y, advance, pixels))
    if reader.remaining:
        msg = f"{reader.remaining} bytes follow the last glyph record"
        raise FormatError(msg)
    drawn = _drawn_records(glyphs, offsets)
    for index, (code, offset) in enumerate(table):
        if offset != drawn[code]:
            msg = (
                f"Entry {index} (U+{code:04X}) points at offset {offset}, "
                f"not at the last record of its code at {drawn[code]}"
            )
            raise FormatError(msg)
    return TnofFont((first, second, third), tuple(glyphs))


def encode_tnof(font: TnofFont) -> bytes:
    """Return the TNOF file of a font, each entry pointing at the last record of its code.

    Args:
        font: The font to write.
    """
    records = BinaryWriter()
    offsets = []
    start = _TABLE_OFFSET + 8 * len(font.glyphs)
    for glyph in font.glyphs:
        if len(glyph.pixels) != glyph.width * glyph.height:
            msg = (
                f"Glyph U+{glyph.code:04X} has {len(glyph.pixels)} pixels "
                f"for {glyph.width} by {glyph.height}"
            )
            raise ValueError(msg)
        offsets.append(start + len(records))
        try:
            records.pack(
                _RECORD,
                glyph.width,
                glyph.height,
                glyph.bearing_x,
                glyph.bearing_y,
                glyph.advance,
            )
        except ValueError as error:
            msg = (
                f"Glyph U+{glyph.code:04X} needs a size and an advance from 0 to 255 "
                "and bearings from -128 to 127"
            )
            raise ValueError(msg) from error
        records.write(glyph.pixels)
    drawn = _drawn_records(font.glyphs, offsets)
    writer = BinaryWriter()
    writer.write(_MAGIC)
    writer.pack("5I", *font.header, _TABLE_OFFSET, len(font.glyphs))
    for glyph in font.glyphs:
        writer.pack("II", glyph.code, drawn[glyph.code])
    writer.write(records.getvalue())
    return writer.getvalue()


def export_tnof(font: TnofFont, directory: Path) -> None:
    """Write font.json and a greyscale PNG per glyph that has pixels.

    Args:
        font: The font to write.
        directory: The folder to write the files to.
    """
    rows: list[dict[str, Any]] = []
    names = _image_names([glyph.code for glyph in font.glyphs])
    for glyph, name in zip(font.glyphs, names, strict=True):
        row: dict[str, Any] = {
            "code": f"U+{glyph.code:04X}",
            "bearing_x": glyph.bearing_x,
            "bearing_y": glyph.bearing_y,
            "advance": glyph.advance,
        }
        if glyph.pixels:
            image = Image.frombytes("L", (glyph.width, glyph.height), glyph.pixels)
            write_png(directory / _IMAGES / name, image)
        else:
            row |= {"width": glyph.width, "height": glyph.height}
        rows.append(row)
    write_json(directory / _DOCUMENT, {"header": list(font.header), "glyphs": rows})


def import_tnof(directory: Path) -> TnofFont:
    """Read a font written by export_tnof, sorting the glyphs by code.

    Args:
        directory: The folder export_tnof wrote.
    """
    return import_json(
        directory / _DOCUMENT, lambda document: _font(document, directory), encode_tnof
    )


def _font(document: Any, directory: Path) -> TnofFont:
    """Return the font of font.json, with the glyph images in directory."""
    first, second, third = document["header"]
    rows = document["glyphs"]
    codes = [_code(row["code"]) for row in rows]
    glyphs = (
        _read_glyph(row, code, directory / _IMAGES / name)
        for row, code, name in zip(rows, codes, _image_names(codes), strict=True)
    )
    return TnofFont((first, second, third), tuple(sorted(glyphs, key=lambda glyph: glyph.code)))


def _drawn_records(glyphs: Sequence[Glyph], offsets: Sequence[int]) -> dict[int, int]:
    """Return the offset of the last record of each code, the one the table names."""
    return {glyph.code: offset for glyph, offset in zip(glyphs, offsets, strict=True)}


def _image_names(codes: Sequence[int]) -> list[str]:
    """Name the PNG of each glyph after its code, marking records never drawn."""
    later = Counter(codes)
    names = []
    for code in codes:
        later[code] -= 1
        unused = f".unused{later[code]}" if later[code] else ""
        names.append(f"U+{code:04X}{unused}.png")
    return names


def _code(text: str) -> int:
    """Read a code point written as U+XXXX."""
    if not (match := _CODE.fullmatch(text)):
        msg = f"{text!r} is not a code point written as U+XXXX"
        raise ValueError(msg)
    return int(match[1], 16)


def _read_glyph(row: dict[str, Any], code: int, image_path: Path) -> Glyph:
    """Return a glyph of font.json, whose size it gives only when it has no image."""
    if "width" in row or "height" in row:
        width, height = row["width"], row["height"]
        if width * height:
            msg = f"U+{code:04X} has no image, so it must be 0 wide or 0 high"
            raise ValueError(msg)
        pixels = b""
    else:
        image = read_image(image_path).convert("RGBA")
        # Drawn on transparency, coverage is what shows over the black backdrop.
        backdrop = Image.new("RGBA", image.size, "black")
        drawn = Image.alpha_composite(backdrop, image)
        (width, height), pixels = image.size, drawn.convert("L").tobytes()
    return Glyph(code, width, height, row["bearing_x"], row["bearing_y"], row["advance"], pixels)
