"""The console font (.cfon): the glyph boxes in its texture and each character's glyph.

Big-endian. A fixed header, each glyph's box in the texture as u0, v0, u1, v1
floats from 0 to 1, then arrays that each start with their length: a word per
glyph, the glyph of each ASCII code, the glyphs and keys of the two-, three- and
four-byte UTF-8 sequences (a key is the sequence as a number, the keys sorted),
and a word per ASCII code. The texture's path closes the file, after its length.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mgtools.binary import BinaryReader, BinaryWriter, ByteOrder
from mgtools.errors import FormatError
from mgtools.fileio import is_index, write_json
from mgtools.mc.roundtrip import ensure_rebuilds, import_json

_HEADER = b"FONT" + bytes.fromhex("00000005 0000000a 00000002 41500000")
_ASCII = 128
# The words of unknown meaning are the same for every glyph and every ASCII code.
_GLYPH_WORD = 0
_ASCII_WORD = 1
_KEY_FORMATS = {2: "H", 3: "I", 4: "I"}

type Box = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class ConsoleFont:
    """The glyph boxes, the glyph each character uses, and the texture's path."""

    glyphs: tuple[Box, ...]
    characters: dict[str, int]
    texture: str


def decode_font(data: bytes) -> ConsoleFont:
    """Read a console font, refusing one that would not encode back to the same bytes.

    Args:
        data: The contents of a .cfon file.
    """
    reader = BinaryReader(data, ByteOrder.BIG)
    if reader.read(len(_HEADER)) != _HEADER:
        raise FormatError("Not a console font of the Master Collection")
    glyphs = tuple(reader.iter_unpack("4f", reader.u32() // 4))
    _read_array(reader, "H")
    characters = {chr(code): glyph for code, glyph in enumerate(_read_array(reader, "H"))}
    for size, key_format in _KEY_FORMATS.items():
        sequences = _read_array(reader, "H")
        keys = _read_array(reader, key_format)
        for key, glyph in zip(keys, sequences, strict=True):
            characters[_character(key, size)] = glyph
    _read_array(reader, "H")
    texture = reader.read(reader.u8()).decode("ascii")
    font = ConsoleFont(glyphs, characters, texture)
    return ensure_rebuilds(data, font, encode_font, "console font")


def encode_font(font: ConsoleFont) -> bytes:
    """Return the .cfon file of a console font, with the arrays that follow from it.

    Args:
        font: The font to write, with a glyph for every ASCII character.
    """
    by_size: dict[int, list[str]] = {size: [] for size in range(1, 5)}
    for character, glyph in sorted(font.characters.items()):
        if len(character) != 1:
            msg = f"{character!r} is not one character"
            raise ValueError(msg)
        if not is_index(glyph, len(font.glyphs)):
            count = len(font.glyphs)
            msg = f"{character!r} uses glyph {glyph!r}, but the font has {count}"
            raise ValueError(msg)
        by_size[len(character.encode())].append(character)
    if len(by_size[1]) != _ASCII:
        raise ValueError("Every ASCII character, U+0000 to U+007F included, needs a glyph")
    writer = BinaryWriter(ByteOrder.BIG)
    writer.write(_HEADER)
    writer.u32(4 * len(font.glyphs))
    for box in font.glyphs:
        writer.pack("4f", *box)
    _write_array(writer, "H", [_GLYPH_WORD] * len(font.glyphs))
    _write_array(writer, "H", [font.characters[c] for c in by_size[1]])
    for size, key_format in _KEY_FORMATS.items():
        _write_array(writer, "H", [font.characters[c] for c in by_size[size]])
        _write_array(writer, key_format, [int.from_bytes(c.encode()) for c in by_size[size]])
    _write_array(writer, "H", [_ASCII_WORD] * _ASCII)
    texture = font.texture.encode("ascii")
    writer.u8(len(texture))
    writer.write(texture)
    return writer.getvalue()


def export_font(font: ConsoleFont, path: Path) -> None:
    """Write a console font as JSON.

    Args:
        font: The font to write.
        path: The JSON file to write.
    """
    write_json(
        path,
        {
            "texture": font.texture,
            "glyphs": [list(box) for box in font.glyphs],
            "characters": dict(sorted(font.characters.items())),
        },
    )


def import_font(path: Path) -> ConsoleFont:
    """Read a console font, refusing one that would not encode.

    Args:
        path: The JSON file export_font wrote.
    """
    return import_json(path, _font, encode_font)


def _font(document: Any) -> ConsoleFont:
    """Return the console font of a JSON document."""
    glyphs = tuple(
        (float(u0), float(v0), float(u1), float(v1)) for u0, v0, u1, v1 in document["glyphs"]
    )
    return ConsoleFont(glyphs, dict(document["characters"]), document["texture"])


def _read_array(reader: BinaryReader, fmt: str) -> tuple[int, ...]:
    return reader.unpack(f"{reader.u32()}{fmt}")


def _write_array(writer: BinaryWriter, fmt: str, values: list[int]) -> None:
    writer.u32(len(values))
    writer.pack(f"{len(values)}{fmt}", *values)


def _character(key: int, size: int) -> str:
    """Return the character of a UTF-8 sequence of size bytes stored as a number."""
    try:
        return key.to_bytes(size).decode()
    except (OverflowError, UnicodeDecodeError) as error:
        msg = f"{key:#x} is not a UTF-8 sequence of {size} bytes"
        raise FormatError(msg) from error
