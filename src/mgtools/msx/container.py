"""The node tree every MSX resource file is made of.

A node is a big-endian u32 header, 2 flag bits above a 30-bit payload size,
followed by its payload. Flags 0 mark a leaf, whose payload is opaque; flags 1
mark a container, whose payload is exactly a sequence of nodes. A resource file
is one container. The engine takes any non-zero flags for a container, but the
games only use 1, so 2 and 3 are refused to keep every rebuild byte for byte.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from mgtools.binary import BinaryReader, ByteOrder
from mgtools.errors import FormatError

_SIZE_MASK = 0x3FFF_FFFF
_CONTAINER = 1 << 30


@dataclass(frozen=True, slots=True)
class Leaf:
    """A node whose payload is opaque."""

    data: bytes


@dataclass(frozen=True, slots=True)
class Container:
    """A node whose payload is its children."""

    children: tuple[Node, ...]


type Node = Leaf | Container


def decode_node(data: bytes) -> Node:
    """Decode data that is exactly one node, such as a whole resource file.

    Args:
        data: The bytes of the node.
    """
    match decode_nodes(data):
        case (node,):
            return node
        case nodes:
            msg = f"Expected exactly one node, found {len(nodes)}"
            raise FormatError(msg)


def decode_nodes(data: bytes) -> tuple[Node, ...]:
    """Decode data that is exactly a sequence of nodes.

    Args:
        data: The bytes of the nodes.
    """
    return _read_nodes(BinaryReader(data, ByteOrder.BIG), len(data))


def encode_node(node: Node) -> bytes:
    """Return the bytes of a node: its header, then its payload.

    Args:
        node: The node to encode, with its children.
    """
    match node:
        case Leaf(data):
            header, payload = 0, data
        case Container(children):
            header, payload = _CONTAINER, encode_nodes(children)
    if len(payload) > _SIZE_MASK:
        msg = f"A node holds at most {_SIZE_MASK} bytes, not {len(payload)}"
        raise ValueError(msg)
    return (header | len(payload)).to_bytes(4, "big") + payload


def encode_nodes(nodes: Iterable[Node]) -> bytes:
    """Return the bytes of a sequence of nodes, one after another.

    Args:
        nodes: The nodes to encode.
    """
    return b"".join(encode_node(node) for node in nodes)


def _read_nodes(reader: BinaryReader, end: int) -> tuple[Node, ...]:
    """Read the nodes from the reader's position up to end, where their parent ends."""
    nodes: list[Node] = []
    while reader.position < end:
        start = reader.position
        header = reader.u32()
        size = header & _SIZE_MASK
        if size > end - reader.position:
            msg = f"The node at offset {start} runs past the end of its parent at {end}"
            raise FormatError(msg)
        match header >> 30:
            case 0:
                nodes.append(Leaf(reader.read(size)))
            case 1:
                nodes.append(Container(_read_nodes(reader, reader.position + size)))
            case flags:
                msg = f"The node at offset {start} has the unknown flags {flags}"
                raise FormatError(msg)
    return tuple(nodes)
