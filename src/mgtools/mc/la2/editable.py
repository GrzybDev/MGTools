"""The editable form of a 2D layout: JSON, with indices in place of offsets.

Items and animations, which the file points at by offset, are named by their
0-based index; node parents and the sprite and font of an item keep the file's
1-based indices.
"""

from dataclasses import asdict
from itertools import batched
from pathlib import Path
from typing import Any

from mgtools.binary import BinaryReader, ByteOrder, packer
from mgtools.fileio import write_json
from mgtools.mc.la2.codec import encode_layout, pack
from mgtools.mc.la2.model import (
    SHOW,
    SHOW_AT,
    TEXT,
    Glyph,
    Item,
    Layout,
    Node,
    Record,
    Show,
    Text,
    Track,
)
from mgtools.mc.roundtrip import (
    code_text,
    colour_text,
    import_json,
    parse_code,
    parse_colour,
)

_LINE_BREAK = 0x0A
_TEXT_STYLE = 24
# Item records shown field by field in the editable form: struct format and names.
_ITEM_FIELDS = {7: ("I", ("sprite",)), 24: ("hHI", ("tracking", "align", "font"))}


def export_layout(layout: Layout, path: Path) -> None:
    """Write a layout as JSON.

    Args:
        layout: The layout to write.
        path: The JSON file to write.
    """
    write_json(
        path,
        {
            "flags": layout.flags,
            "atlases": [code_text(code) for code in layout.atlases],
            "scene": layout.scene,
            "nodes": [_node_json(node) for node in layout.nodes],
            "items": [[_item_record_json(r) for r in item] for item in layout.items],
            "animations": [
                [_track_json(track) for track in animation] for animation in layout.animations
            ],
            "animation_names": [
                {"name": code_text(name), "animation": index}
                for name, index in layout.animation_names
            ],
            "sprites": [
                {"sprite": code_text(sprite), "atlas": code_text(atlas)}
                for sprite, atlas in layout.sprites
            ],
            "colours": [
                [colour_text(bytes(c)) for c in batched(colours, 4, strict=True)]
                for colours in layout.colours
            ],
            "table6": [_record_json(record) for record in layout.table6],
            "table7": [_record_json(record) for record in layout.table7],
            "fonts": [[_glyph_json(glyph) for glyph in font] for font in layout.fonts],
        },
    )


def import_layout(path: Path) -> Layout:
    """Read an exported layout, checking that its fonts have a glyph for every text.

    Args:
        path: The JSON file export_layout wrote.
    """
    return import_json(path, _layout, encode_layout)


def _check_text(layout: Layout, index: int, item: Item) -> None:
    """Refuse an item whose text uses a code that the font of its style lacks."""
    text = next((r.data for r in item if isinstance(r, Text)), None)
    style = next((r for r in item if isinstance(r, Record) and r.type == _TEXT_STYLE), None)
    if text is None or style is None:
        return
    (font,) = BinaryReader(style.data).unpack("4xI")
    if not 0 < font <= len(layout.fonts):
        msg = f"Item {index} uses font {font}, but the layout has {len(layout.fonts)}"
        raise ValueError(msg)
    codes = {glyph.code for glyph in layout.fonts[font - 1]} | {_LINE_BREAK}
    if missing := sorted(set(text) - codes):
        characters = bytes(missing).decode("latin-1")
        msg = f"Item {index}: font {font} has no glyph for {characters!r}"
        raise ValueError(msg)


def _node_json(node: Node) -> dict[str, Any]:
    value = asdict(node) | {"name": code_text(node.name)}
    if not node.refs:
        del value["refs"]
    return value


def _record_json(record: Record) -> dict[str, Any]:
    return {"type": record.type, "data": record.data.hex()}


def _item_record_json(record: Record | Text) -> dict[str, Any]:
    """Return a record of an item as JSON, with the fields of known records by name."""
    if isinstance(record, Text):
        return {"type": TEXT, "text": record.data.decode("latin-1")}
    if view := _ITEM_FIELDS.get(record.type):
        fmt, names = view
        if len(record.data) == packer(ByteOrder.LITTLE, fmt).size:
            values = BinaryReader(record.data).unpack(fmt)
            return {"type": record.type} | dict(zip(names, values, strict=True))
    return _record_json(record)


def _track_json(track: Track) -> dict[str, Any]:
    records = [_track_record_json(record) for record in track.records]
    return {"target": track.target, "end": track.end, "records": records}


def _track_record_json(record: Record | Show) -> dict[str, Any]:
    if isinstance(record, Record):
        return _record_json(record)
    if record.time is None:
        return {"type": SHOW, "item": record.item}
    return {"type": SHOW_AT, "time": record.time, "item": record.item}


def _glyph_json(glyph: Glyph) -> dict[str, Any]:
    value = asdict(glyph)
    return {"char": chr(value.pop("code"))} | value


def _layout(document: Any) -> Layout:
    """Return the layout of a JSON document, checking the glyphs of its texts."""
    layout = Layout(
        document["flags"],
        tuple(map(parse_code, document["atlases"])),
        tuple(document["scene"]),
        tuple(map(_node_of, document["nodes"])),
        tuple(
            tuple(_item_record_of(index, record) for record in item)
            for index, item in enumerate(document["items"])
        ),
        tuple(tuple(map(_track_of, animation)) for animation in document["animations"]),
        tuple((parse_code(n["name"]), n["animation"]) for n in document["animation_names"]),
        tuple((parse_code(s["sprite"]), parse_code(s["atlas"])) for s in document["sprites"]),
        tuple(b"".join(map(parse_colour, colours)) for colours in document["colours"]),
        tuple(map(_record_of, document["table6"])),
        tuple(map(_record_of, document["table7"])),
        tuple(tuple(map(_glyph_of, font)) for font in document["fonts"]),
    )
    for index, item in enumerate(layout.items):
        _check_text(layout, index, item)
    return layout


def _node_of(value: Any) -> Node:
    refs = tuple((a, b) for a, b in value.get("refs", ()))
    return Node(**(value | {"name": parse_code(value["name"]), "refs": refs}))


def _record_of(value: Any) -> Record:
    return Record(value["type"], bytes.fromhex(value["data"]))


def _item_record_of(index: int, value: Any) -> Record | Text:
    """Return a record of item index from JSON: a text, named fields or hex data."""
    kind = value["type"]
    if kind == TEXT:
        try:
            return Text(value["text"].encode("latin-1"))
        except UnicodeEncodeError as error:
            char = error.object[error.start]
            msg = f"Item {index}: texts take Latin-1 characters, not {char!r} (U+{ord(char):04X})"
            raise ValueError(msg) from error
    if kind in _ITEM_FIELDS and "data" not in value:
        fmt, names = _ITEM_FIELDS[kind]
        return Record(kind, pack(fmt, *(value[name] for name in names)))
    return _record_of(value)


def _track_of(value: Any) -> Track:
    records = tuple(map(_track_record_of, value["records"]))
    return Track(value["target"], records, value["end"])


def _track_record_of(value: Any) -> Record | Show:
    if value["type"] == SHOW:
        return Show(value["item"])
    if value["type"] == SHOW_AT:
        return Show(value["item"], value["time"])
    return _record_of(value)


def _glyph_of(value: Any) -> Glyph:
    box = {name: number for name, number in value.items() if name != "char"}
    return Glyph(**box, code=ord(value["char"]))
