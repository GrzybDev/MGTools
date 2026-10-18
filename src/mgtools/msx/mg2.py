"""The resource file of Metal Gear 2: Solid Snake.

Its 49 sections hold, by index: sprite animations, whose block 42 is the cell
atlas (0), game tables (1), the text (2), scripts (3), area data (4-23), sprite
sheets (24), shared tile sheets (25), the tile sheets of each area (26-45),
palettes (46), two screens (47) and the font (48). The cell atlas lists
rectangles of the sprite sheets in groups; a cell's slot is its sheet plus 3.

The game keeps one 256-colour table and loads palettes into parts of it as the
screen changes, so the colours of an image depend on where it is drawn.
"""

from collections.abc import Sequence
from itertools import batched

from mgtools.errors import FormatError, located
from mgtools.msx.container import Leaf, decode_nodes, encode_nodes
from mgtools.msx.game import Game
from mgtools.msx.images import Clut, decode_rectangles, encode_rectangles
from mgtools.msx.layout import Layout, Leaves, Position, position_name
from mgtools.msx.palette import MAX_COLOURS, Colour

_CELLS = (0, 42)
_SPRITE_SETS = (1, 6)
_SET_SIZE = 82
"""Flags per sprite set: whether it loads each sheet, then an end marker."""
_SPRITES = 24
# Slots 0 to 2 are not sprite sheets; the 81 sheets follow.
_SLOTS = range(3 + 81)
_SHARED_TILES = 25
_AREA_TILES = range(26, 46)

type _Loads = tuple[tuple[int, int], ...]
"""Palettes and the index of the colour table each is loaded at."""

_TITLE: _Loads = ((41, 0), (37, 96))
_IN_GAME: _Loads = ((41, 0), (36, 64), (39, 96))
_VERSUS: _Loads = ((41, 0), (36, 64), (40, 96))
_ENDING: _Loads = ((41, 0), (36, 64), (37, 96))
_TITLE_SET = 21
_LAST_AREA_SET = 17
_VERSUS_SET = 22
# Only the ending draws these sheets, though the last area's set loads them.
_ENDING_SHEETS = frozenset({35, 42, 43, 66})
_TILE_COLOURS = 192
_SHARED_TILE_PALETTE = 33
_AREA_TILE_PALETTES = (
    0,
    1,
    3,
    5,
    7,
    9,
    11,
    13,
    15,
    16,
    17,
    19,
    21,
    23,
    25,
    26,
    27,
    28,
    29,
    31,
)


def _clut(position: Position, palettes: Sequence[Sequence[Colour]], leaves: Leaves) -> Clut | None:
    """Return the colour table the game shows a sprite or tile sheet with, None elsewhere."""
    match position:
        case (section, sheet) if section == _SPRITES:
            loads = _sheet_loads(sheet, leaves)
        case (section, sheet) if section == _SHARED_TILES:
            loads = ((_SHARED_TILE_PALETTE + sheet, _TILE_COLOURS),)
        case (section, sheet) if section in _AREA_TILES:
            first = _AREA_TILE_PALETTES[section - _AREA_TILES.start]
            loads = ((first + sheet, _TILE_COLOURS),)
        case _:
            return None
    clut: list[Colour | None] = [None] * MAX_COLOURS
    for palette, start in loads:
        if palette >= len(palettes):
            msg = f"{position_name(position)} shows palette {palette}, which is missing"
            raise ValueError(msg)
        colours = palettes[palette]
        if start + len(colours) > MAX_COLOURS:
            msg = (
                f"Palette {palette} has {len(colours)} colours, but the game loads it "
                f"at index {start}, which leaves room for {MAX_COLOURS - start}"
            )
            raise ValueError(msg)
        clut[start : start + len(colours)] = colours
    return clut


def _sheet_loads(sheet: int, leaves: Leaves) -> _Loads:
    """Return the palettes a sprite sheet shows, by the sprite sets that load it."""
    if (table := leaves.get(_SPRITE_SETS)) is None:
        msg = f"The sprite sets, {position_name(_SPRITE_SETS)}, are missing"
        raise ValueError(msg)
    sets = {
        number
        for number, flags in enumerate(batched(table, _SET_SIZE, strict=False))
        if sheet < len(flags) and flags[sheet]
    }
    if _TITLE_SET in sets:
        return _TITLE
    if sheet in _ENDING_SHEETS and _LAST_AREA_SET in sets:
        return _ENDING
    if _VERSUS_SET in sets:
        return _VERSUS
    return _IN_GAME


def _export_cells(leaves: Leaves) -> tuple[object, list[Position]]:
    """Return the cell groups of the atlas as JSON, and the position of the atlas."""
    if (data := leaves.get(_CELLS)) is None:
        msg = f"The cell atlas, {position_name(_CELLS)}, is missing"
        raise FormatError(msg)
    groups = []
    for number, node in enumerate(decode_nodes(data)):
        cells = decode_rectangles(node.data, "slot", _SLOTS) if isinstance(node, Leaf) else None
        if cells is None:
            msg = f"Cell group {number} is not a table of numbered cells"
            raise FormatError(msg)
        groups.append(cells)
    return groups, [_CELLS]


def _import_cells(value: object) -> dict[Position, bytes]:
    """Build the cell atlas from the JSON that _export_cells gives."""
    if not isinstance(value, list):
        msg = "The cells must be a list of groups"
        raise ValueError(msg)
    groups = []
    for number, cells in enumerate(value):
        with located(f"Cell group {number}"):
            groups.append(Leaf(encode_rectangles(cells, "slot", _SLOTS)))
    return {_CELLS: encode_nodes(groups)}


LAYOUT = Layout(
    game=Game.MG2,
    kinds=(
        "animations",
        "tables",
        "text",
        "scripts",
        *["area"] * 20,
        "sprite sheets",
        "tiles",
        *["area tiles"] * 20,
        "palettes",
        "screens",
        "font",
    ),
    text=2,
    font=48,
    palettes=46,
    screens=47,
    clut=_clut,
    rectangles="cells.json",
    export_rectangles=_export_cells,
    import_rectangles=_import_cells,
)
