"""The model of a 2D layout: its scene, items, animations and fonts."""

from dataclasses import dataclass

# The record types held as a Text or a Show rather than as a Record.
TEXT = 13
SHOW = 7
SHOW_AT = 8


@dataclass(frozen=True, slots=True)
class Node:
    """A scene node; parent is the 1-based index of an earlier node, 0 for the root."""

    name: int
    kind: int
    parent: int
    unknown: int
    refs: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class Record:
    """A typed record whose payload is kept as it is."""

    type: int
    data: bytes


@dataclass(frozen=True, slots=True)
class Text:
    """An item's text: the codes of its glyphs and line breaks."""

    data: bytes


@dataclass(frozen=True, slots=True)
class Show:
    """A track record that shows an item, at a time when it has one."""

    item: int
    time: int | None = None


@dataclass(frozen=True, slots=True)
class Track:
    """A track of an animation: the records it plays on its target."""

    target: int
    records: tuple[Record | Show, ...]
    end: int
    """The type of the record closing the track: 0, or 3 on a few tracks."""


@dataclass(frozen=True, slots=True)
class Glyph:
    """A glyph: its size, its box in the font's sprite (0 to 65535) and its code."""

    width: int
    height: int
    u0: int
    u1: int
    v0: int
    v1: int
    code: int


type Item = tuple[Record | Text, ...]
type Animation = tuple[Track, ...]


@dataclass(frozen=True, slots=True)
class Layout:
    """A layout, without the counts, sizes and offsets that follow from it."""

    flags: int
    atlases: tuple[int, ...]
    scene: tuple[int, ...]
    """The five words of the scene header that are not counts, of unknown meaning."""
    nodes: tuple[Node, ...]
    items: tuple[Item, ...]
    animations: tuple[Animation, ...]
    animation_names: tuple[tuple[int, int], ...]
    """The strcode naming each named animation, and its index."""
    sprites: tuple[tuple[int, int], ...]
    """The strcodes of each sprite and of its atlas."""
    colours: tuple[bytes, ...]
    """Records of RGBA colours."""
    table6: tuple[Record, ...]
    table7: tuple[Record, ...]
    fonts: tuple[tuple[Glyph, ...], ...]
