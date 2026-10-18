"""TXTR textures (.ctxr): 8-bit BGRA texels and their mipmaps.

A big-endian header of 128 bytes gives the version (7, or 5 for the console
font), the size, the pixel format (only 0, BGRA, occurs), whether any texel of
level 0 is translucent, the per-channel minimum and maximum of level 0 in RGBA
order, and the level count: 1, or a full chain down to 1x1. Each level is a u32
size and its texels, padded with zeros to the next 32-byte file offset.

The editable form is a PNG of level 0 with the alpha as stored (many textures
use the PS2 scale, where 0x80 is opaque) and a JSON file of the settings.
"""

from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import Any

from PIL import Image

from mgtools.binary import BinaryReader, BinaryWriter, ByteOrder
from mgtools.errors import FormatError
from mgtools.fileio import read_image, write_json, write_png
from mgtools.mc.roundtrip import (
    colour_text,
    ensure_rebuilds,
    import_json,
    parse_colour,
)

_MAGIC = b"TXTR"
_HEADER_SIZE = 0x80
_ALIGNMENT = 32
# Constant bytes between the colour range and the level count, by version.
_FILLERS = {5: bytes(4), 7: b"\xff\xff" + bytes(5)}


@dataclass(frozen=True, slots=True)
class Texture:
    """A texture's levels of BGRA texels, from its full size down."""

    version: int
    width: int
    height: int
    levels: tuple[bytes, ...]


def decode_texture(data: bytes) -> Texture:
    """Read a texture, refusing one that would not encode back to the same bytes.

    Args:
        data: The contents of a .ctxr file.
    """
    reader = BinaryReader(data, ByteOrder.BIG)
    header = BinaryReader(reader.read(_HEADER_SIZE), ByteOrder.BIG)
    magic, version, width, height, _, _, pixel_format = header.unpack("4sI5H")
    if magic != _MAGIC:
        raise FormatError("Not a TXTR texture")
    filler = _filler(version)
    if pixel_format:
        msg = f"Pixel format {pixel_format} is not supported, only 0 (BGRA)"
        raise FormatError(msg)
    count = data[0x1F + len(filler)]
    if count not in (1, max(width, height).bit_length()):
        msg = f"A {width}x{height} texture cannot have {count} levels"
        raise FormatError(msg)
    if count > 1 and not _powers_of_two(width, height):
        msg = (
            f"Mipmaps of a {width}x{height} texture are not supported; "
            "MGTools remakes mipmaps only for power-of-two sides"
        )
        raise FormatError(msg)
    levels = []
    for level in range(count):
        size = reader.u32()
        level_width, level_height = _level_size(width, height, level)
        if size != 4 * level_width * level_height:
            texels = f"{level_width}x{level_height}"
            msg = f"Level {level} has {size} bytes for {texels} texels"
            raise FormatError(msg)
        levels.append(reader.read(size))
        reader.read(-reader.position % _ALIGNMENT)
    texture = Texture(version, width, height, tuple(levels))
    return ensure_rebuilds(data, texture, encode_texture, "texture")


def encode_texture(texture: Texture) -> bytes:
    """Return the .ctxr file of a texture, with the header that follows from its texels.

    Args:
        texture: The texture to write.
    """
    low, high = _colour_range(texture.levels[0])
    writer = BinaryWriter(ByteOrder.BIG)
    writer.write(_MAGIC)
    writer.pack("I5H", texture.version, texture.width, texture.height, 1, 0, 0)
    writer.pack("B4x", low[3] != 0xFF)
    writer.write(low + high + _filler(texture.version))
    writer.u8(len(texture.levels))
    writer.write(bytes(_HEADER_SIZE - len(writer)))
    for level in texture.levels:
        writer.u32(len(level))
        writer.write(level)
        writer.write(bytes(-len(writer) % _ALIGNMENT))
    return writer.getvalue()


def mipmaps(level0: bytes, width: int, height: int) -> list[bytes]:
    """Return levels 1 and up, each texel the floored mean of its block of level 0.

    Args:
        level0: The BGRA texels of the full-size level.
        width: The width of level 0, a power of two.
        height: The height of level 0, a power of two.
    """
    if not _powers_of_two(width, height):
        msg = f"Only textures with power-of-two sides have mipmaps, not {width}x{height}"
        raise ValueError(msg)
    sums = [list(level0[channel::4]) for channel in range(4)]
    area = 1
    levels = []
    while width > 1 or height > 1:
        if width > 1:
            sums = [[a + b for a, b in zip(s[::2], s[1::2], strict=True)] for s in sums]
            width //= 2
            area *= 2
        if height > 1:
            sums = [
                [
                    a + b
                    for top, bottom in batched(batched(s, width, strict=True), 2, strict=True)
                    for a, b in zip(top, bottom, strict=True)
                ]
                for s in sums
            ]
            height //= 2
            area *= 2
        level = bytearray(4 * width * height)
        for channel, values in enumerate(sums):
            level[channel::4] = bytes(value // area for value in values)
        levels.append(bytes(level))
    return levels


def export_texture(texture: Texture, path: Path) -> None:
    """Write level 0 as a PNG at path, and the settings as JSON next to it.

    Args:
        texture: The texture to write.
        path: The PNG file to write.
    """
    size = (texture.width, texture.height)
    write_png(path, Image.frombytes("RGBA", size, texture.levels[0], "raw", "BGRA"))
    settings: dict[str, Any] = {
        "version": texture.version,
        "mipmaps": len(texture.levels) > 1,
    }
    if overrides := _overrides(texture):
        settings["mipmap_overrides"] = overrides
    write_json(path.with_suffix(".json"), settings)


def import_texture(path: Path) -> Texture:
    """Build a texture from an exported PNG, remaking its mipmaps from level 0.

    Args:
        path: The PNG file export_texture wrote, with its JSON settings next to it.
    """
    rgba = read_image(path).convert("RGBA")
    return import_json(
        path.with_suffix(".json"),
        lambda settings: _texture(rgba, settings),
        encode_texture,
    )


def _texture(image: Image.Image, settings: Any) -> Texture:
    """Return the texture of an exported image and its JSON settings."""
    width, height = image.size
    levels = [image.tobytes("raw", "BGRA")]
    if settings["mipmaps"]:
        made = [bytearray(level) for level in mipmaps(levels[0], width, height)]
        for override in settings.get("mipmap_overrides", []):
            _restore(made, width, height, override)
        levels += map(bytes, made)
    return Texture(settings["version"], width, height, tuple(levels))


def _overrides(texture: Texture) -> list[dict[str, Any]]:
    """List the mipmap texels the game's converter rounded unlike mipmaps()."""
    if len(texture.levels) == 1:
        return []
    made = mipmaps(texture.levels[0], texture.width, texture.height)
    found = []
    for level, (computed, shipped) in enumerate(zip(made, texture.levels[1:], strict=True), 1):
        if computed == shipped:
            continue
        width, _ = _level_size(texture.width, texture.height, level)
        for start in range(0, len(computed), 4):
            ours, theirs = computed[start : start + 4], shipped[start : start + 4]
            if ours != theirs:
                y, x = divmod(start // 4, width)
                found.append(
                    {
                        "level": level,
                        "x": x,
                        "y": y,
                        "computed": _colour(ours),
                        "shipped": _colour(theirs),
                    }
                )
    return found


def _restore(made: list[bytearray], width: int, height: int, override: Any) -> None:
    """Put a shipped texel back unless an edit of level 0 changed what it replaces."""
    level, x, y = override["level"], override["x"], override["y"]
    if not 0 < level <= len(made):
        return
    level_width, level_height = _level_size(width, height, level)
    if 0 <= x < level_width and 0 <= y < level_height:
        texels = made[level - 1]
        start = 4 * (y * level_width + x)
        if texels[start : start + 4] == _texel(override["computed"]):
            texels[start : start + 4] = _texel(override["shipped"])


def _filler(version: int) -> bytes:
    """Return the constant bytes before the level count, refusing unknown versions."""
    if version not in _FILLERS:
        msg = f"TXTR version {version} is not supported, only 5 and 7"
        raise FormatError(msg)
    return _FILLERS[version]


def _colour(texel: bytes) -> str:
    """Return a BGRA texel as #rrggbbaa."""
    blue, green, red, alpha = texel
    return colour_text(bytes((red, green, blue, alpha)))


def _texel(colour: str) -> bytes:
    """Return the BGRA texel of a colour written as #rrggbbaa."""
    red, green, blue, alpha = parse_colour(colour)
    return bytes((blue, green, red, alpha))


def _colour_range(texels: bytes) -> tuple[bytes, bytes]:
    """Return the per-channel minimum and maximum of BGRA texels, in RGBA order."""
    channels = [texels[channel::4] for channel in (2, 1, 0, 3)]
    return bytes(map(min, channels)), bytes(map(max, channels))


def _powers_of_two(width: int, height: int) -> bool:
    return not (width & (width - 1) or height & (height - 1))


def _level_size(width: int, height: int, level: int) -> tuple[int, int]:
    return max(1, width >> level), max(1, height >> level)
