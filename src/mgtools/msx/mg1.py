"""The resource file of Metal Gear.

Its 77 sections hold, by index: tile sets (0-17: tile flags of sets A and B, then
the images of A, A dark, B and B dark), rooms (20-37), actors (40), sprite sheets
(41-70: images, then an empty record), a script (71), the text (72), a table per
area (73), the palette of every image (74), the font (75) and two screens (76).
Record 0 of most actors lists the rectangles of their frames in the sprite sheets.
"""

from collections.abc import Sequence

from mgtools.errors import located
from mgtools.msx.game import Game
from mgtools.msx.images import Clut, decode_rectangles, encode_rectangles
from mgtools.msx.layout import Layout, Leaves, Position
from mgtools.msx.palette import Colour

_TILESETS = range(18)
_ACTORS = 40
_SPRITES = range(41, 71)


def _clut(position: Position, palettes: Sequence[Sequence[Colour]], _: Leaves) -> Clut | None:
    """Return the one palette for tile set and sprite sheet images, None elsewhere."""
    match position:
        # Records 0 and 1 of a tile set are the flags of its tiles.
        case (section, record) if section in _SPRITES or (section in _TILESETS and record >= 2):
            if len(palettes) != 1:
                msg = f"Metal Gear has one palette, not {len(palettes)}"
                raise ValueError(msg)
            return palettes[0]
    return None


def _export_actors(leaves: Leaves) -> tuple[object, list[Position]]:
    """Return the rectangles of each actor's frames by actor number, and their positions."""
    actors: dict[str, object] = {}
    for position, data in leaves.items():
        if position[0] == _ACTORS and position[2:] == (0,) and data:
            rectangles = decode_rectangles(data, "sheet", _SPRITES)
            if rectangles is not None:
                actors[str(position[1])] = rectangles
    return actors, [(_ACTORS, int(actor), 0) for actor in actors]


def _import_actors(value: object) -> dict[Position, bytes]:
    """Build record 0 of each actor from the JSON that _export_actors gives."""
    if not isinstance(value, dict):
        msg = "The actors must map actor numbers to rectangles"
        raise ValueError(msg)
    leaves: dict[Position, bytes] = {}
    for actor, rectangles in value.items():
        if not (actor.isascii() and actor.isdigit()):
            msg = f"{actor!r} is not an actor number"
            raise ValueError(msg)
        with located(f"Actor {actor}"):
            leaves[_ACTORS, int(actor), 0] = encode_rectangles(rectangles, "sheet", _SPRITES)
    return leaves


LAYOUT = Layout(
    game=Game.MG1,
    kinds=(
        *["tile set"] * 18,
        *["unused"] * 2,
        *["rooms"] * 18,
        *["unused"] * 2,
        "actors",
        *["sprite sheet"] * 30,
        "script",
        "text",
        "area table",
        "palette",
        "font",
        "screens",
    ),
    text=72,
    font=75,
    palettes=74,
    screens=76,
    clut=_clut,
    rectangles="actors.json",
    export_rectangles=_export_actors,
    import_rectangles=_import_actors,
)
