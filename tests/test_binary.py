from collections.abc import Callable

import pytest

from mgtools.binary import BinaryReader, BinaryWriter, ByteOrder
from mgtools.errors import FormatError


@pytest.mark.parametrize(
    ("byte_order", "data"),
    [
        (ByteOrder.LITTLE, b"\x01\x02\x00\x03\x00\x00\x00"),
        (ByteOrder.BIG, b"\x01\x00\x02\x00\x00\x00\x03"),
    ],
)
def test_values_are_written_and_read_in_the_byte_order_of_the_instance(
    byte_order: ByteOrder, data: bytes
) -> None:
    writer = BinaryWriter(byte_order)
    writer.u8(1)
    writer.u16(2)
    writer.u32(3)
    reader = BinaryReader(data, byte_order)

    assert writer.getvalue() == data
    assert [reader.u8(), reader.u16(), reader.u32()] == [1, 2, 3]
    assert reader.remaining == 0


@pytest.mark.parametrize("size", [5, -1])
def test_reading_past_the_end_names_the_offset(size: int) -> None:
    reader = BinaryReader(b"\x00\x01\x02\x03")
    reader.u16()

    with pytest.raises(FormatError, match=f"needed {size} bytes at offset 2, 2 left"):
        reader.read(size)
    assert reader.position == 2


def test_records_are_read_together_or_not_at_all() -> None:
    reader = BinaryReader(b"\x01\x00\x02\x00\x03\x00", ByteOrder.LITTLE)

    with pytest.raises(FormatError, match="needed 8 bytes"):
        list(reader.iter_unpack("H", 4))
    assert list(reader.iter_unpack("H", 3)) == [(1,), (2,), (3,)]


@pytest.mark.parametrize(
    ("write", "value"),
    [(BinaryWriter.u8, 256), (BinaryWriter.u16, -1)],
)
def test_values_out_of_range_are_refused(
    write: Callable[[BinaryWriter, int], None], value: int
) -> None:
    writer = BinaryWriter()

    with pytest.raises(ValueError, match=f"Cannot write .*{value}"):
        write(writer, value)
    assert len(writer) == 0
