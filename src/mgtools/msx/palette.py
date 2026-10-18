"""The palettes of the MSX games.

A palette stores each colour as four bytes: blue, green, red and one the games
ignore, always 0. Exported palettes are JSON lists of "#rrggbb" colours.
"""

import re
from collections.abc import Iterable, Sequence
from itertools import batched
from pathlib import Path

from mgtools.errors import FormatError, located
from mgtools.fileio import convert_json, write_json

type Colour = tuple[int, int, int]
"""Red, green and blue, from 0 to 255."""

MAX_COLOURS = 256
_COLOUR_NAME = re.compile(r"#[0-9A-Fa-f]{6}")


def decode_palette(data: bytes) -> list[Colour]:
    """Return the colours of a palette.

    Args:
        data: The bytes of the palette.
    """
    if len(data) % 4:
        msg = f"A palette takes 4 bytes per colour, which {len(data)} bytes are not"
        raise FormatError(msg)
    colours: list[Colour] = []
    for blue, green, red, unused in batched(data, 4, strict=True):
        if unused:
            msg = f"Colour {len(colours)} of the palette has {unused} in its unused byte"
            raise FormatError(msg)
        colours.append((red, green, blue))
    return colours


def encode_palette(colours: Iterable[Colour]) -> bytes:
    """Return the bytes of a palette.

    Args:
        colours: The colours of the palette.
    """
    return b"".join(bytes((blue, green, red, 0)) for red, green, blue in colours)


def colour_name(colour: Colour) -> str:
    """Write a colour as #rrggbb.

    Args:
        colour: The colour to write.
    """
    return "#{:02x}{:02x}{:02x}".format(*colour)


def parse_colour(name: object) -> Colour:
    """Read a colour written #rrggbb.

    Args:
        name: The value read from JSON.
    """
    if not isinstance(name, str) or not _COLOUR_NAME.fullmatch(name):
        msg = f"{name!r} is not a colour written #rrggbb"
        raise ValueError(msg)
    value = int(name[1:], 16)
    return value >> 16, value >> 8 & 0xFF, value & 0xFF


def export_palettes(palettes: Iterable[Sequence[Colour]], path: Path) -> None:
    """Write palettes as a JSON list of lists of #rrggbb colours.

    Args:
        palettes: The palettes to write.
        path: The JSON file to write.
    """
    write_json(path, [[colour_name(colour) for colour in palette] for palette in palettes])


def import_palettes(path: Path) -> list[list[Colour]]:
    """Read the palettes that export_palettes wrote.

    Args:
        path: The JSON file to read.
    """
    return convert_json(path, _palettes)


def _palettes(value: object) -> list[list[Colour]]:
    """Return the palettes of a JSON value, refusing what a palette cannot hold."""
    if not isinstance(value, list) or not all(isinstance(p, list) for p in value):
        msg = "Not a list of palettes"
        raise ValueError(msg)
    palettes = []
    for number, palette in enumerate(value):
        with located(f"Palette {number}"):
            if len(palette) > MAX_COLOURS:
                msg = f"It has {len(palette)} colours, more than {MAX_COLOURS}"
                raise ValueError(msg)
            palettes.append([parse_colour(name) for name in palette])
    return palettes
