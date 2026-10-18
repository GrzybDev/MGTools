"""PS2 sprite atlases (.tri): the GS registers that cut each sprite from a texture page.

Little-endian. A 32-byte header, a 192-byte entry per sprite, then GS memory for
the texture pages and their palettes, in rows of 256 bytes. The Master Collection
draws each sprite from the HD texture its strcode names, so that memory is all
zero. An entry holds the sprite's texture coordinates and quad, which follow from
its TEX0 and CLAMP registers, its strcode, a flag of unknown meaning, and five GS
registers as A+D pairs behind a constant GIFtag.
"""

from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mgtools.binary import BinaryReader, BinaryWriter
from mgtools.errors import FormatError, located
from mgtools.fileio import is_index, write_json
from mgtools.mc.roundtrip import (
    code_text,
    ensure_rebuilds,
    import_json,
    parse_code,
)

_HEADER_SIZE = 0x20
_ENTRY_SIZE = 192
_ROW_SIZE = 256
_GIFTAG = bytes.fromhex("0180000000000070eeeefe0f00000000")
_REGION_CLAMP = 2
# The quads stop just short of the texel edges, in float32 like on the PS2.
_INSET = array("f", [0.4999])[0]

type Fields = tuple[tuple[str, int, int], ...]
type Register = dict[str, int]


def _fields(layout: str) -> Fields:
    """Read the fields of a register, written as name:lowest bit:width."""
    return tuple(
        (name, int(shift), int(width))
        for name, shift, width in (field.split(":") for field in layout.split())
    )


_TEX = _fields(
    "TBP0:0:14 TBW:14:6 PSM:20:6 TW:26:4 TH:30:4 TCC:34:1 TFX:35:2 CBP:37:14 "
    "CPSM:51:4 CSM:55:1 CSA:56:5 CLD:61:3"
)
# Entries hold these registers in this order, each with its GS address.
_REGISTERS = (
    (
        "TEX1_1",
        0x14,
        _fields("LCM:0:1 MXL:2:3 MMAG:5:1 MMIN:6:3 MTBA:9:1 L:19:2 K:32:12"),
    ),
    ("TEX2_1", 0x16, _TEX),
    ("TEX0_1", 0x06, _TEX),
    ("ALPHA_1", 0x42, _fields("A:0:2 B:2:2 C:4:2 D:6:2 FIX:32:8")),
    (
        "CLAMP_1",
        0x08,
        _fields("WMS:0:2 WMT:2:2 MINU:4:10 MAXU:14:10 MINV:24:10 MAXV:34:10"),
    ),
)


@dataclass(frozen=True, slots=True)
class Sprite:
    """A sprite: the strcode of its HD texture, and its GS registers by name."""

    code: int
    flag: int
    registers: dict[str, Register]


@dataclass(frozen=True, slots=True)
class Atlas:
    """The sprites of an atlas and the rows of GS memory its pages and palettes take."""

    image_rows: int
    palette_rows: int
    unknown: int
    sprites: tuple[Sprite, ...]


def decode_atlas(data: bytes) -> Atlas:
    """Read a sprite atlas, refusing one that would not encode back to the same bytes.

    Args:
        data: The contents of a .tri file.
    """
    reader = BinaryReader(data)
    _, image_rows, _, palette_rows, count, unknown, _, palettes = reader.unpack("8I")
    # The format has no magic number, but the header gives the file's size.
    if len(data) != palettes + _ROW_SIZE * palette_rows:
        raise FormatError("Not a sprite atlas: its header gives another size")
    sprites = []
    for _ in range(count):
        entry = BinaryReader(reader.read(_ENTRY_SIZE))
        # The coordinates follow from the registers; the rebuild checks them along
        # with the constant parts of the entry.
        _, code, _, flag = entry.unpack("16s3I")
        entry.read(0x50 - entry.position)
        registers = {}
        for name, _, fields in _REGISTERS:
            value, _ = entry.unpack("2Q")
            registers[name] = {
                field: (value >> shift) & ((1 << bits) - 1) for field, shift, bits in fields
            }
        sprites.append(Sprite(code, flag, registers))
    atlas = Atlas(image_rows, palette_rows, unknown, tuple(sprites))
    return ensure_rebuilds(data, atlas, encode_atlas, "sprite atlas")


def encode_atlas(atlas: Atlas) -> bytes:
    """Return the .tri file of an atlas, with blank GS memory and coordinates from the registers.

    Args:
        atlas: The atlas to write.
    """
    count = len(atlas.sprites)
    image_offset = (_HEADER_SIZE + _ENTRY_SIZE * count + 0x7F) & ~0x7F
    palette_offset = image_offset + _ROW_SIZE * atlas.image_rows
    writer = BinaryWriter()
    writer.pack("5I", 0, atlas.image_rows, atlas.image_rows, atlas.palette_rows, count)
    writer.pack("3I", atlas.unknown, image_offset, palette_offset)
    for index, sprite in enumerate(atlas.sprites):
        with located(f"Sprite {index}"):
            _write_sprite(writer, sprite)
    writer.write(bytes(palette_offset + _ROW_SIZE * atlas.palette_rows - len(writer)))
    return writer.getvalue()


def export_atlas(atlas: Atlas, path: Path) -> None:
    """Write an atlas as JSON, each sprite's registers field by field.

    Args:
        atlas: The atlas to write.
        path: The JSON file to write.
    """
    write_json(
        path,
        {
            "image_rows": atlas.image_rows,
            "palette_rows": atlas.palette_rows,
            "unknown": atlas.unknown,
            "sprites": [
                {
                    "code": code_text(sprite.code),
                    "flag": sprite.flag,
                    **sprite.registers,
                }
                for sprite in atlas.sprites
            ],
        },
    )


def import_atlas(path: Path) -> Atlas:
    """Read an atlas, refusing one that would not encode.

    Args:
        path: The JSON file export_atlas wrote.
    """
    return import_json(path, _atlas, encode_atlas)


def _atlas(document: Any) -> Atlas:
    """Return the atlas of a JSON document."""
    sprites = tuple(
        Sprite(
            parse_code(sprite["code"]),
            sprite["flag"],
            {name: dict(sprite[name]) for name, _, _ in _REGISTERS},
        )
        for sprite in document["sprites"]
    )
    return Atlas(document["image_rows"], document["palette_rows"], document["unknown"], sprites)


def _write_sprite(writer: BinaryWriter, sprite: Sprite) -> None:
    registers = [
        (_register(name, fields, sprite.registers[name]), address)
        for name, address, fields in _REGISTERS
    ]
    tex0, clamp = sprite.registers["TEX0_1"], sprite.registers["CLAMP_1"]
    u, width = _span("U", clamp["WMS"], clamp["MINU"], clamp["MAXU"], tex0["TW"])
    v, height = _span("V", clamp["WMT"], clamp["MINV"], clamp["MAXV"], tex0["TH"])
    writer.pack("4f", u, v, width, height)
    writer.pack("3I2H", sprite.code, 0, sprite.flag, tex0["TBP0"], tex0["CBP"])
    writer.write(bytes(32) + _GIFTAG)
    for register in registers:
        writer.pack("2Q", *register)
    centre = (u + width / 2, v + height / 2)
    writer.pack("8f", -width * _INSET, -height * _INSET, 1, 1, *centre, 0, 0)


def _span(axis: str, mode: int, low: int, high: int, size_log2: int) -> tuple[float, float]:
    """Return where a sprite starts on one axis of its page, and how far it reaches."""
    if mode != _REGION_CLAMP:
        return 0.0, 1.0
    size = 1 << size_log2
    if not low <= high < size:
        msg = (
            f"CLAMP_1 MIN{axis} {low} and MAX{axis} {high} must be in order within "
            f"its page, {size} texels across"
        )
        raise ValueError(msg)
    return (low + 0.5) / size, (high - low) / size


def _register(name: str, fields: Fields, values: Register) -> int:
    """Return the 64-bit value of a register, refusing a field too wide for its bits."""
    value = 0
    for field, shift, bits in fields:
        number = values[field]
        if not is_index(number, 1 << bits):
            msg = f"{name} {field} takes {bits} bits, not {number!r}"
            raise ValueError(msg)
        value |= number << shift
    return value
