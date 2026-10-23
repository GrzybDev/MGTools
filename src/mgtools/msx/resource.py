"""Exporting the resource files of the MSX games to folders people edit, and back.

A folder holds each leaf of the file's node tree once, named by its position in
the tree: images as PNGs in images/, palettes in palettes.json, the rectangles of
the sprites' frames in the game's JSON file, text and font as msx.text writes
them, and every other leaf as a .bin file in raw/. resource.json names the game,
the containers without leaves, and the colours of images that RGB copies need to
find their palette indices again.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mgtools.errors import FormatError, located
from mgtools.fileio import convert_json, is_index, write_atomically, write_json
from mgtools.msx import mg1, mg2
from mgtools.msx.charset import Charmap
from mgtools.msx.container import Container, Leaf, Node, decode_node, encode_node
from mgtools.msx.game import Game
from mgtools.msx.images import (
    colour_choices,
    decode_image,
    encode_image,
    export_image,
    export_screen,
    import_image,
    import_screen,
)
from mgtools.msx.layout import Layout, Position, parse_position, position_name
from mgtools.msx.palette import (
    MAX_COLOURS,
    Colour,
    colour_name,
    decode_palette,
    encode_palette,
    export_palettes,
    import_palettes,
    parse_colour,
)
from mgtools.msx.text import export_text_and_font, import_text_and_font
from mgtools.translation import TranslationFormat

_LAYOUTS = {layout.game: layout for layout in (mg1.LAYOUT, mg2.LAYOUT)}
_MANIFEST = "resource.json"
_PALETTES = "palettes.json"
_IMAGES = "images"
_RAW = "raw"


@dataclass(frozen=True, slots=True)
class Section:
    """What a section of a resource file holds, in how many leaves and bytes."""

    kind: str
    leaves: int
    size: int


def describe_resource(data: bytes) -> tuple[Game, list[Section]]:
    """Return the game of a resource file and what each of its sections holds.

    Args:
        data: The bytes of the resource file.
    """
    layout, root = _open(data)
    return layout.game, [
        Section(
            kind,
            sum(isinstance(node, Leaf) for _, node in _ends(section)),
            len(encode_node(section)),
        )
        for kind, section in zip(layout.kinds, root.children, strict=True)
    ]


def export_resource(
    data: bytes,
    directory: Path,
    fmt: TranslationFormat,
    charmap: Charmap | None = None,
    *,
    separate_glyphs: bool = False,
) -> None:
    """Export a resource file to a new or empty folder, its text in a format.

    Args:
        data: The bytes of the resource file.
        directory: The new or empty folder to write to.
        fmt: The format of the text for translation tools.
        charmap: The characters of the single-byte codes, None for those of the release.
        separate_glyphs: Whether to save each font glyph as its own image instead of a PNG
            per page.
    """
    layout, root = _open(data)
    # Import takes every file it finds, so files of another export would end up
    # in the resource file.
    if directory.is_dir() and any(directory.iterdir()):
        msg = f"{directory} is not empty: export into a new or empty folder"
        raise FileExistsError(msg)
    ends = dict(_ends(root))
    leaves = {p: node.data for p, node in ends.items() if isinstance(node, Leaf)}
    exported: set[Position] = set()

    def section(index: int) -> dict[Position, bytes]:
        """Return the leaves of a section, counting them as exported."""
        children = {p: data for p, data in leaves.items() if p[0] == index}
        exported.update(children)
        return children

    text, font = section(layout.text), section(layout.font)
    export_text_and_font(
        layout.game,
        [*text.values()],
        [*font.values()],
        directory,
        fmt,
        charmap,
        separate_glyphs=separate_glyphs,
    )
    palettes = []
    for position, palette in section(layout.palettes).items():
        with located(position_name(position)):
            palettes.append(decode_palette(palette))
    export_palettes(palettes, directory / _PALETTES)
    for position, screen in section(layout.screens).items():
        with located(position_name(position)):
            export_screen(screen, _image_path(directory, position))
    rectangles, positions = layout.export_rectangles(leaves)
    write_json(directory / layout.rectangles, rectangles)
    exported.update(positions)
    choices: dict[str, dict[str, int]] = {}
    for position, data in leaves.items():
        clut = layout.clut(position, palettes, leaves)
        if clut is None or not data:
            continue
        with located(position_name(position)):
            image = decode_image(data)
        export_image(image, clut, _image_path(directory, position))
        if chosen := colour_choices(image, clut):
            names = {colour_name(colour): index for colour, index in chosen.items()}
            choices[position_name(position)] = names
        exported.add(position)
    for position, data in leaves.items():
        if position not in exported:
            write_atomically(directory / _RAW / f"{position_name(position)}.bin", data)
    empty = [position_name(p) for p, node in ends.items() if isinstance(node, Container)]
    manifest: dict[str, object] = {"game": layout.game}
    if empty:
        manifest["empty_containers"] = empty
    if choices:
        manifest["colour_choices"] = choices
    write_json(directory / _MANIFEST, manifest)


def import_resource(directory: Path) -> bytes:
    """Build a resource file from a folder that export_resource wrote.

    Args:
        directory: The folder to read.
    """
    layout, empty, choices = convert_json(directory / _MANIFEST, _manifest)
    leaves: dict[Position, bytes] = {}

    def add(position: Position, data: bytes) -> None:
        """Keep a leaf, refusing a position held twice or past the last section."""
        if position in leaves:
            msg = f"{directory} holds {position_name(position)} twice"
            raise ValueError(msg)
        if position[0] >= len(layout.kinds):
            msg = (
                f"{directory} holds {position_name(position)}, but the last "
                f"section is {len(layout.kinds) - 1}"
            )
            raise ValueError(msg)
        leaves[position] = data

    for position, path in _named_files(directory / _RAW, "*.bin"):
        add(position, path.read_bytes())
    palettes = import_palettes(directory / _PALETTES)
    for index, palette in enumerate(palettes):
        add((layout.palettes, index), encode_palette(palette))
    rectangles = convert_json(directory / layout.rectangles, layout.import_rectangles)
    for position, data in rectangles.items():
        add(position, data)
    text, font = import_text_and_font(layout.game, directory)
    for section, blocks in ((layout.text, text), (layout.font, font)):
        for index, block in enumerate(blocks):
            add((section, index), block)
    for position, path in _named_files(directory / _IMAGES, "*.png"):
        if position[0] == layout.screens:
            add(position, import_screen(path))
        elif (clut := layout.clut(position, palettes, leaves)) is not None:
            image = import_image(path, clut, choices.get(position, {}))
            add(position, encode_image(image))
        else:
            msg = f"{path}: {position_name(position)} holds no image"
            raise ValueError(msg)
    nodes: dict[Position, Node] = {p: Leaf(data) for p, data in leaves.items()}
    for position in empty:
        if position in nodes:
            msg = (
                f"{directory} holds {position_name(position)} both as a file and "
                f"as an empty container of {_MANIFEST}"
            )
            raise ValueError(msg)
        nodes[position] = Container(())
    with located(directory):
        root = Container(_children(nodes))
    if len(root.children) != len(layout.kinds):
        msg = f"{directory} holds {len(root.children)} sections, not {len(layout.kinds)}"
        raise ValueError(msg)
    return encode_node(root)


def _open(data: bytes) -> tuple[Layout, Container]:
    """Decode a resource file, telling its game by its number of sections."""
    problem = "Not a resource file of Metal Gear (77 sections) or Metal Gear 2 (49)"
    try:
        root = decode_node(data)
    except FormatError as error:
        msg = f"{problem}: {error}"
        raise FormatError(msg) from error
    match root:
        case Container(sections) if all(isinstance(section, Container) for section in sections):
            for layout in _LAYOUTS.values():
                if len(sections) == len(layout.kinds):
                    return layout, root
    raise FormatError(problem)


def _ends(node: Node, position: Position = ()) -> Iterator[tuple[Position, Node]]:
    """Yield the leaves and empty containers of a tree, by position."""
    match node:
        case Container(children) if children:
            for index, child in enumerate(children):
                yield from _ends(child, (*position, index))
        case _:
            yield position, node


def _children(nodes: Mapping[Position, Node], parent: Position = ()) -> tuple[Node, ...]:
    """Rebuild the children of a container from the nodes by their relative position."""
    groups: dict[int, dict[Position, Node]] = {}
    for (index, *path), node in nodes.items():
        groups.setdefault(index, {})[tuple(path)] = node
    children: list[Node] = []
    for index in range(len(groups)):
        position = (*parent, index)
        if index not in groups:
            msg = f"No file holds {position_name(position)}"
            raise ValueError(msg)
        group = groups[index]
        if () not in group:
            children.append(Container(_children(group, position)))
        elif len(group) == 1:
            children.append(group[()])
        else:
            msg = f"Files hold both {position_name(position)} and nodes inside it"
            raise ValueError(msg)
    return tuple(children)


def _manifest(
    manifest: Any,
) -> tuple[Layout, list[Position], dict[Position, dict[Colour, int]]]:
    """Return the layout, empty containers and colour choices resource.json gives."""
    layout = _LAYOUTS[Game(manifest["game"])]
    empty = [parse_position(name) for name in manifest.get("empty_containers", [])]
    choices = {
        parse_position(name): {parse_colour(colour): index for colour, index in colours.items()}
        for name, colours in manifest.get("colour_choices", {}).items()
    }
    for colours in choices.values():
        if not all(is_index(i, MAX_COLOURS) for i in colours.values()):
            msg = "It chooses palette indices outside 0 to 255"
            raise ValueError(msg)
    return layout, empty, choices


def _named_files(folder: Path, pattern: str) -> Iterator[tuple[Position, Path]]:
    """Yield the files of a folder that match a pattern, with the position each names."""
    for path in sorted(folder.glob(pattern)):
        with located(path):
            position = parse_position(path.stem)
        yield position, path


def _image_path(directory: Path, position: Position) -> Path:
    return directory / _IMAGES / f"{position_name(position)}.png"
