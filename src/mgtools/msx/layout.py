"""Positions in the node tree of a resource file, and what each game keeps where."""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from mgtools.msx.game import Game
from mgtools.msx.images import Clut
from mgtools.msx.palette import Colour

type Position = tuple[int, ...]
"""The indices leading from the root of the tree to a node, section first."""

type Leaves = Mapping[Position, bytes]

_POSITION_NAME = re.compile(r"\d{2,}(\.\d{3,})*")


def position_name(position: Position) -> str:
    """Name a position as files do, such as 71.005 for leaf 5 of section 71.

    Args:
        position: The position to name.
    """
    section, *path = position
    return f"{section:02d}" + "".join(f".{index:03d}" for index in path)


def parse_position(name: str) -> Position:
    """Return the position a file name gives, such as 71.005.

    Args:
        name: The name, as position_name writes it.
    """
    if not _POSITION_NAME.fullmatch(name):
        msg = f"{name!r} does not name a position, such as 71.005"
        raise ValueError(msg)
    return tuple(int(index) for index in name.split("."))


@dataclass(frozen=True, slots=True)
class Layout:
    """What a game keeps in each section of its resource file, known by index alone.

    The fields text, font, palettes and screens give the index of their section.
    """

    game: Game
    kinds: tuple[str, ...]
    """What each section holds."""
    text: int
    font: int
    palettes: int
    screens: int
    clut: Callable[[Position, Sequence[Sequence[Colour]], Leaves], Clut | None]
    """The colours of the image at a position, or None where the game keeps none."""
    rectangles: str
    """The JSON file of the rectangles the sprites' frames take in their sheets."""
    export_rectangles: Callable[[Leaves], tuple[object, list[Position]]]
    """The rectangles as JSON, and the positions of the leaves they come from."""
    import_rectangles: Callable[[object], dict[Position, bytes]]
    """The leaves built from the rectangles' JSON, by position."""
