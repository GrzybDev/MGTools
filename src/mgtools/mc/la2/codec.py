"""The .la2 file of a 2D layout.

Little-endian, with absolute offsets. A header of section offsets and atlas
strcodes, then nine sections: the scene's node tree, the items (lists of typed
records, such as a text and the font and sprite it is drawn with), the
animations (tracks of records, some of which show an item), the animation names,
the sprites (sprite and atlas strcodes), the colours, two tables of records of
unknown meaning, and the fonts. A font is a glyph table: a text's bytes are the
codes of its glyphs, except line breaks.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import astuple
from itertools import accumulate, pairwise

from mgtools.binary import BinaryReader, BinaryWriter
from mgtools.errors import FormatError
from mgtools.fileio import is_index
from mgtools.mc.la2.model import (
    SHOW,
    SHOW_AT,
    TEXT,
    Animation,
    Glyph,
    Item,
    Layout,
    Node,
    Record,
    Show,
    Text,
    Track,
)
from mgtools.mc.roundtrip import ensure_rebuilds

_VERSION = 7
_HEADER_SIZE = 0x34
_FLAGS_SHIFT = 28
_SCENE_WORDS = 22
_KINDS = 11
_DELAY = 4
_EVENT = 1
_TRACK_ENDS = (0, 3)
_REFERRING_KIND = 9
# Byte 6 and word 0x0E of a node follow from its kind; kind 9 sums its refs instead.
_KIND_BYTES = {0: 1, 1: 1, 2: 2, 3: 6, 6: 0, 7: 0, 8: 0, 9: 0, 10: 14}
_KIND_WEIGHTS = {6: 4, 7: 2, 8: 5}


def decode_layout(data: bytes) -> Layout:
    """Read a layout, refusing one that would not encode back to the same bytes.

    Args:
        data: The contents of a .la2 file.
    """
    header = BinaryReader(data)
    version, _, header_word = header.unpack("2HI")
    if version != _VERSION:
        msg = f"Not a layout of version {_VERSION}, but of version {version}"
        raise FormatError(msg)
    s1, s2, s3, _, _, s4, s5, s6, s7, s8 = header.unpack("10I")
    atlases = header.unpack(f"{header.u32()}I")
    start = header_word & ((1 << _FLAGS_SHIFT) - 1)
    bounds = (start, s1, s2, s3, s4, s5, s6, s7, s8, len(data))
    sections = [BinaryReader(data[a:b]) for a, b in pairwise(bounds)]

    scene = sections[0].unpack(f"{_SCENE_WORDS}H")
    nodes = tuple(_read_node(sections[0]) for _ in range(scene[0]))

    items, item_at = [], {}
    reader = sections[1]
    for index in range(reader.u32()):
        item_at[s1 + reader.position] = index
        _, size = reader.unpack("2H")
        records = _read_records(BinaryReader(reader.read(size - 4)))
        if not records or records.pop() != (0, b""):
            msg = f"Item {index} does not end with an end record"
            raise FormatError(msg)
        items.append(tuple(_item_record(kind, payload) for kind, payload in records))

    animations, animation_at = [], {}
    reader = sections[2]
    for index in range(reader.u32()):
        animation_at[s2 + reader.position] = index
        count, size = reader.unpack("2I")
        tracks = BinaryReader(reader.read(size - 8))
        animations.append(tuple(_read_track(tracks, item_at, index) for _ in range(count)))

    reader = sections[3]
    names = tuple(
        (name, _index_at(animation_at, offset, "animation"))
        for name, offset in reader.iter_unpack("2I", reader.u32())
    )
    reader = sections[4]
    sprites = tuple(reader.iter_unpack("2I", reader.u32()))
    tables = [_read_table(section) for section in sections[5:8]]
    reader = sections[8]
    fonts = []
    for _ in range(reader.u32()):
        _, count, _ = reader.unpack("I2H")
        glyphs = reader.iter_unpack("6HI", count)
        fonts.append(tuple(Glyph(*glyph) for glyph in glyphs))

    layout = Layout(
        header_word >> _FLAGS_SHIFT,
        atlases,
        scene[3:8],
        nodes,
        tuple(items),
        tuple(animations),
        names,
        sprites,
        tuple(payload for _, payload in tables[0]),
        tuple(Record(*record) for record in tables[1]),
        tuple(Record(*record) for record in tables[2]),
        tuple(fonts),
    )
    return ensure_rebuilds(data, layout, encode_layout, "layout")


def encode_layout(layout: Layout) -> bytes:
    """Return the .la2 file of a layout, with the counts and offsets that follow from it.

    Args:
        layout: The layout to write.
    """
    start = _HEADER_SIZE + 4 * len(layout.atlases)
    nodes = _encode_nodes(layout)
    items, item_offsets = _counted_blocks(map(_item_bytes, layout.items), start + len(nodes))
    animations, animation_offsets = _counted_blocks(
        (_animation_bytes(animation, item_offsets) for animation in layout.animations),
        start + len(nodes) + len(items),
    )
    names = [
        (name, _offset(animation_offsets, index, "animation"))
        for name, index in layout.animation_names
    ]
    glyphs = BinaryWriter()
    glyphs.u32(len(layout.fonts))
    for font in layout.fonts:
        glyphs.pack("I2H", 0, len(font), 8 + 16 * len(font))
        for glyph in font:
            glyphs.pack("6HI", *astuple(glyph))
    sections = [
        nodes,
        items,
        animations,
        _counted_pairs(names),
        _counted_pairs(layout.sprites),
        _counted_records((len(colours) // 4, colours) for colours in layout.colours),
        _counted_records((r.type, r.data) for r in layout.table6),
        _counted_records((r.type, r.data) for r in layout.table7),
        glyphs.getvalue(),
    ]
    s0, s1, s2, s3, s4, s5, s6, s7, s8, end = accumulate(map(len, sections), initial=start)
    writer = BinaryWriter()
    writer.pack("2HI", _VERSION, 1, layout.flags << _FLAGS_SHIFT | s0)
    writer.pack("10I", s1, s2, s3, 0x30, 0, s4, s5, s6, s7, s8)
    writer.u32(len(layout.atlases))
    writer.pack(f"{len(layout.atlases)}I", *layout.atlases)
    for section in sections:
        writer.write(section)
    writer.write(bytes(-end % 16))
    return writer.getvalue()


def _read_node(reader: BinaryReader) -> Node:
    name, kind, _, unknown, _, parent, _, _, count = reader.unpack("IH2B4HI")
    return Node(name, kind, parent, unknown, tuple(reader.iter_unpack("2H", count)))


def _read_records(reader: BinaryReader) -> list[tuple[int, bytes]]:
    records = []
    while reader.remaining:
        kind, size = reader.unpack("2H")
        records.append((kind, reader.read(size - 4)))
    return records


def _read_table(reader: BinaryReader) -> list[tuple[int, bytes]]:
    """Read a section of counted records; the rebuild checks the count."""
    reader.u32()
    return _read_records(reader)


def _item_record(kind: int, payload: bytes) -> Record | Text:
    """Return a record of an item, reading a text record as its Text."""
    if kind == TEXT:
        reader = BinaryReader(payload)
        return Text(reader.read(reader.u32()))
    return Record(kind, payload)


def _read_track(reader: BinaryReader, item_at: dict[int, int], animation: int) -> Track:
    target, _, size = reader.unpack("2HI")
    records = _read_records(BinaryReader(reader.read(size - 8)))
    if not records or records[-1][0] not in _TRACK_ENDS or records[-1][1]:
        msg = f"A track of animation {animation} does not end with an end record"
        raise FormatError(msg)
    end, _ = records.pop()
    return Track(target, tuple(_track_record(k, p, item_at) for k, p in records), end)


def _track_record(kind: int, payload: bytes, item_at: dict[int, int]) -> Record | Show:
    """Return a record of a track, reading a show record as a Show of an item's index."""
    if kind not in (SHOW, SHOW_AT):
        return Record(kind, payload)
    reader = BinaryReader(payload)
    time = reader.u32() if kind == SHOW_AT else None
    return Show(_index_at(item_at, reader.u32(), "item"), time)


def _index_at(starts: dict[int, int], offset: int, kind: str) -> int:
    """Return the index of the item or animation of kind that starts at offset."""
    if offset not in starts:
        msg = f"No {kind} starts at offset {offset:#x}"
        raise FormatError(msg)
    return starts[offset]


def _encode_nodes(layout: Layout) -> bytes:
    nodes = layout.nodes
    weights = [_weight(index, node) for index, node in enumerate(nodes, 1)]
    kinds = Counter(node.kind for node in nodes)
    writer = BinaryWriter()
    # Node count, weight of kinds 8 and 9, ref count, the unknown words, count of
    # kind 10, count of each kind, and two zero words.
    writer.pack(
        f"{_SCENE_WORDS}H",
        len(nodes),
        sum(w for n, w in zip(nodes, weights, strict=True) if n.kind in (8, 9)),
        sum(len(node.refs) for node in nodes),
        *layout.scene,
        kinds[10],
        *(kinds[kind] for kind in range(_KINDS)),
        0,
        0,
    )
    ends = _ends(nodes)
    for index, (node, weight) in enumerate(zip(nodes, weights, strict=True), 1):
        byte = _KIND_BYTES[node.kind]
        links = (index, node.parent, ends[index - 1], weight)
        writer.pack("IH2B4HI", node.name, node.kind, byte, node.unknown, *links, len(node.refs))
        for ref in node.refs:
            writer.pack("2H", *ref)
    return writer.getvalue()


def _weight(index: int, node: Node) -> int:
    """Return word 0x0E of the node of 1-based index, which follows from its kind."""
    if node.kind not in _KIND_BYTES:
        msg = f"Node {index} is of kind {node.kind}, not one of {sorted(_KIND_BYTES)}"
        raise ValueError(msg)
    if node.kind == _REFERRING_KIND:
        return sum(b for _, b in node.refs)
    return _KIND_WEIGHTS.get(node.kind, 1)


def _ends(nodes: tuple[Node, ...]) -> list[int]:
    """Return the index of the first node after each node's subtree, or 0 at the end."""
    last = list(range(1, len(nodes) + 1))
    for index, node in enumerate(nodes, 1):
        if not is_index(node.parent, index):
            msg = f"Node {index} has the parent {node.parent!r}, which is not before it"
            raise ValueError(msg)
        parent = node.parent
        while parent:
            last[parent - 1] = index
            parent = nodes[parent - 1].parent
    return [end + 1 if end < len(nodes) else 0 for end in last]


def _item_bytes(item: Item) -> bytes:
    records = [_item_payload(record) for record in item] + [(0, b"")]
    body = _records(records)
    return pack("2H", len(records), 4 + len(body)) + body


def _item_payload(record: Record | Text) -> tuple[int, bytes]:
    """Return the type and payload of a record of an item."""
    match record:
        case Text(text):
            return TEXT, pack("I", len(text)) + text + bytes(4 - len(text) % 4)
        case Record(kind, payload):
            return kind, payload


def _animation_bytes(animation: Animation, item_offsets: list[int]) -> bytes:
    tracks = b"".join(_track_bytes(track, item_offsets) for track in animation)
    return pack("2I", len(animation), 8 + len(tracks)) + tracks


def _track_bytes(track: Track, item_offsets: list[int]) -> bytes:
    records = [_track_payload(record, item_offsets) for record in track.records]
    records.append((track.end, b""))
    body = _records(records)
    # A delay right before an event makes a single key with it.
    keys = len(records) - sum(a == _DELAY and b == _EVENT for (a, _), (b, _) in pairwise(records))
    return pack("2HI", track.target, keys, 8 + len(body)) + body


def _track_payload(record: Record | Show, item_offsets: list[int]) -> tuple[int, bytes]:
    """Return the type and payload of a record of a track, a Show pointing at its item."""
    if isinstance(record, Record):
        return record.type, record.data
    offset = _offset(item_offsets, record.item, "item")
    if record.time is None:
        return SHOW, pack("I", offset)
    return SHOW_AT, pack("2I", record.time, offset)


def _offset(offsets: list[int], index: int, kind: str) -> int:
    """Return where the item or animation of kind at index starts."""
    if not is_index(index, len(offsets)):
        msg = f"There is no {kind} {index!r}: the layout has {len(offsets)}"
        raise ValueError(msg)
    return offsets[index]


def _counted_blocks(blocks: Iterable[bytes], start: int) -> tuple[bytes, list[int]]:
    """Join blocks after their count, returning where each starts when at start."""
    listed = list(blocks)
    offsets = list(accumulate(map(len, listed), initial=start + 4))[:-1]
    return pack("I", len(listed)) + b"".join(listed), offsets


def _counted_pairs(pairs: Iterable[tuple[int, int]]) -> bytes:
    listed = list(pairs)
    return pack(f"I{2 * len(listed)}I", len(listed), *(v for pair in listed for v in pair))


def _counted_records(records: Iterable[tuple[int, bytes]]) -> bytes:
    listed = list(records)
    return pack("I", len(listed)) + _records(listed)


def _records(records: Iterable[tuple[int, bytes]]) -> bytes:
    """Return records back to back, each its type, its size and its payload."""
    writer = BinaryWriter()
    for kind, payload in records:
        writer.pack("2H", kind, 4 + len(payload))
        writer.write(payload)
    return writer.getvalue()


def pack(fmt: str, *values: int) -> bytes:
    """Return values packed little-endian with a struct format.

    Args:
        fmt: The struct format, without a byte order prefix.
        values: The values to pack.
    """
    writer = BinaryWriter()
    writer.pack(fmt, *values)
    return writer.getvalue()
