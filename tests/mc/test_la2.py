import struct
from dataclasses import replace
from pathlib import Path

import pytest

from mgtools.errors import FormatError
from mgtools.fileio import read_json, write_json
from mgtools.mc.la2.codec import decode_layout, encode_layout
from mgtools.mc.la2.editable import export_layout, import_layout
from mgtools.mc.la2.model import Glyph, Layout, Node, Record, Show, Text, Track

TEXT_ITEM = (
    Record(3, bytes(16)),
    Record(7, struct.pack("<I", 1)),
    Record(24, struct.pack("<hHI", -32, 1, 1)),
    Text(b"AB\nBA"),
)
LAYOUT = Layout(
    flags=1,
    atlases=(0xBB5979,),
    scene=(5, 5, 2, 0, 1),
    nodes=(
        Node(0x2A4634, 0, 0, 1),
        Node(0x123456, 9, 1, 2, ((3, 4), (5, 6))),
        Node(0x234567, 10, 2, 2),
        Node(0x345678, 3, 1, 0),
    ),
    items=(TEXT_ITEM, (Record(1, b""), Record(9, bytes.fromhex("10100000")))),
    animations=(
        (
            Track(3, (Show(0), Record(4, bytes(4)), Record(1, bytes(12)), Show(1, 30)), 0),
            Track(4, (Record(2, bytes.fromhex("4e0e0000")),), 3),
        ),
    ),
    animation_names=((0x5A6ED3, 0),),
    sprites=((0x53C115, 0xBB5979),),
    colours=(bytes.fromhex("ffffff80"), bytes.fromhex("000000ff 80808080")),
    table6=(Record(2, bytes(8)),),
    table7=(Record(4, bytes(4)),),
    fonts=(
        (
            Glyph(16, 20, 0, 2048, 0, 21845, 0x41),
            Glyph(16, 20, 2048, 4096, 0, 21845, 0x42),
        ),
    ),
)


def sections(data: bytes) -> list[int]:
    """Return the offsets of sections 0 to 8 of an encoded layout.

    Args:
        data: The encoded layout.
    """
    s0 = struct.unpack_from("<I", data, 4)[0] & 0xFFFFFFF
    s1, s2, s3, _, _, *s4_to_s8 = struct.unpack_from("<10I", data, 8)
    return [s0, s1, s2, s3, *s4_to_s8]


def test_a_layout_encodes_with_its_derived_counts_and_offsets_and_decodes_back() -> None:
    data = encode_layout(LAYOUT)
    s0, s1, s2, *_ = sections(data)
    first_node = s0 + 44
    nodes = [
        struct.unpack_from("<IH2B4HI", data, offset)
        for offset in (first_node, first_node + 20, first_node + 48, first_node + 68)
    ]
    second_item = s1 + 4 + struct.unpack_from("<2H", data, s1 + 4)[1]
    track = s2 + 12

    assert struct.unpack_from("<2HI", data) == (7, 1, 1 << 28 | 0x38)
    assert struct.unpack_from("<2I", data, 0x14) == (0x30, 0)
    assert struct.unpack_from("<2I", data, 0x30) == (1, 0xBB5979)
    assert len(data) % 16 == 0
    kinds = (1, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1)
    assert struct.unpack_from("<22H", data, s0) == ((4, 10, 2, *LAYOUT.scene, 1, *kinds, 0, 0))
    assert nodes == [
        (0x2A4634, 0, 1, 1, 1, 0, 0, 1, 0),
        (0x123456, 9, 0, 2, 2, 1, 4, 10, 2),
        (0x234567, 10, 14, 2, 3, 2, 4, 1, 0),
        (0x345678, 3, 6, 0, 4, 1, 0, 1, 0),
    ]
    # A delay right before an event counts as one key.
    assert struct.unpack_from("<2HI", data, track)[:2] == (3, 4)
    assert struct.unpack_from("<2HI", data, track + 8) == (7, 8, s1 + 4)
    assert struct.unpack_from("<2H2I", data, track + 40) == (8, 12, 30, second_item)
    assert decode_layout(data) == LAYOUT


def test_a_longer_text_moves_the_items_after_it_and_their_references() -> None:
    longer = replace(LAYOUT, items=((*TEXT_ITEM[:3], Text(b"ABBA ABBA ABBA")), *LAYOUT.items[1:]))

    data = encode_layout(longer)

    # 14 bytes and their padding take 8 more than 5 bytes and theirs.
    before = sections(encode_layout(LAYOUT))
    moved = [new - old for new, old in zip(sections(data), before, strict=True)]
    assert moved == [0, 0, 8, 8, 8, 8, 8, 8, 8]
    assert decode_layout(data) == longer


def test_the_json_shows_texts_text_styles_and_items_by_index(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"

    export_layout(LAYOUT, path)

    document = read_json(path)
    assert document["items"][0][1:] == [
        {"type": 7, "sprite": 1},
        {"type": 24, "tracking": -32, "align": 1, "font": 1},
        {"type": 13, "text": "AB\nBA"},
    ]
    assert document["animations"][0][0]["records"][3] == {
        "type": 8,
        "time": 30,
        "item": 1,
    }
    assert document["fonts"][0][0]["char"] == "A"
    assert import_layout(path) == LAYOUT


def edited(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "layout.json"
    export_layout(LAYOUT, path)
    document = read_json(path)
    document["items"][0][3]["text"] = text
    write_json(path, document)
    return path


def test_an_edited_text_may_break_lines_without_a_glyph_for_them(
    tmp_path: Path,
) -> None:
    layout = import_layout(edited(tmp_path, "BAAB\n\nA"))

    assert layout.items[0][3] == Text(b"BAAB\n\nA")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("ABC", r"Item 0: font 1 has no glyph for 'C'"),
        ("AŁA", r"Item 0: texts take Latin-1 characters, not 'Ł' \(U\+0141\)"),
    ],
)
def test_texts_their_font_cannot_draw_are_refused(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        import_layout(edited(tmp_path, text))


def test_a_colour_not_written_as_rrggbbaa_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"
    export_layout(LAYOUT, path)
    document = read_json(path)
    document["colours"][1][0] = "#000000"
    write_json(path, document)

    with pytest.raises(ValueError, match="'#000000' is not a colour written as"):
        import_layout(path)


@pytest.mark.parametrize(
    ("layout", "message"),
    [
        (
            replace(LAYOUT, animations=((Track(0, (Show(2),), 0),),)),
            "There is no item 2: the layout has 2",
        ),
        (
            replace(LAYOUT, animation_names=((1, 1),)),
            "There is no animation 1: the layout has 1",
        ),
        (
            replace(LAYOUT, nodes=(Node(1, 0, 0, 1), Node(2, 0, 2, 0))),
            "Node 2 has the parent 2, which is not before it",
        ),
        (
            replace(LAYOUT, nodes=(Node(1, 4, 0, 1),)),
            r"Node 1 is of kind 4, not one of \[0, 1, 2, 3, 6, 7, 8, 9, 10\]",
        ),
    ],
)
def test_layouts_with_dangling_links_or_unknown_kinds_are_refused(
    layout: Layout, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        encode_layout(layout)


def test_a_track_pointing_inside_an_item_is_refused() -> None:
    data = bytearray(encode_layout(LAYOUT))
    offset = sections(bytes(data))[2] + 24
    struct.pack_into("<I", data, offset, struct.unpack_from("<I", data, offset)[0] + 4)

    with pytest.raises(FormatError, match="No item starts at offset"):
        decode_layout(bytes(data))


@pytest.mark.parametrize(
    ("offset", "value", "message"),
    [
        (0x14, 0x31, "cannot keep, at offset 0x14"),
        (0x38 + 44 + 4, 4, "cannot keep: Node 1 is of kind 4"),
    ],
)
def test_values_this_tool_cannot_rebuild_are_refused(offset: int, value: int, message: str) -> None:
    data = bytearray(encode_layout(LAYOUT))
    data[offset] = value

    with pytest.raises(FormatError, match=message):
        decode_layout(bytes(data))
