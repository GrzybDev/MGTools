from pathlib import Path

import pytest

from mgtools.errors import FormatError
from mgtools.msx.container import (
    Container,
    Leaf,
    decode_node,
    decode_nodes,
    encode_node,
)

TREE = Container(
    (
        Container((Leaf(b"\x01\x02\x03"), Leaf(b""))),
        Container(()),
        Leaf(b"\xc0"),
    )
)
TREE_BYTES = bytes.fromhex("40000018 4000000b 00000003 010203 00000000 40000000 00000001 c0")


def test_a_tree_is_encoded_with_flagged_sizes_and_decoded_back() -> None:
    assert encode_node(TREE) == TREE_BYTES
    assert decode_node(TREE_BYTES) == TREE


def test_sizes_follow_edits_of_the_payloads() -> None:
    edited = Container((Container((Leaf(b"longer data"),)),))

    assert encode_node(edited) == (bytes.fromhex("40000013 4000000f 0000000b") + b"longer data")


def test_sizes_take_30_bits_below_the_flags() -> None:
    tree = Container((Leaf(bytes(0x0100_0000)),))

    data = encode_node(tree)

    assert data[:8] == bytes.fromhex("41000004 01000000")
    assert decode_node(data) == tree


def test_a_leaf_payload_can_itself_be_read_as_records() -> None:
    records = bytes.fromhex("00000001 61 00000000")

    assert decode_nodes(records) == (Leaf(b"a"), Leaf(b""))


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("40000006 00000003 6162", "node at offset 4 runs past .* at 10"),
        ("40000002 0000", "needed 4 bytes at offset 4, 2 left"),
        ("00000005 616263", "node at offset 0 runs past .* at 7"),
        ("80000000", "offset 0 has the unknown flags 2"),
        ("40000004 c0000000", "offset 4 has the unknown flags 3"),
        ("00000000 00000000", "Expected exactly one node, found 2"),
        ("", "Expected exactly one node, found 0"),
    ],
)
def test_malformed_trees_are_reported(data: str, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        decode_node(bytes.fromhex(data))


def test_every_resource_file_rebuilds_byte_for_byte(
    resource_files: list[Path], subtests: pytest.Subtests
) -> None:
    for path in resource_files:
        with subtests.test(path.as_posix()):
            data = path.read_bytes()

            root = decode_node(data)

            assert isinstance(root, Container)
            assert all(isinstance(section, Container) for section in root.children)
            assert encode_node(root) == data
