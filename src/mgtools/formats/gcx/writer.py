import struct
from io import BytesIO


class Writer:
    """Utility class for writing binary data to a buffer. Provides methods to write various integer sizes and blocks of bytes, as well as some custom size formats used in GCX files."""

    def __init__(self):
        self.buf = BytesIO()

    def tell(self) -> int:
        return self.buf.tell()

    def u8(self, v: int):
        self.buf.write(struct.pack("B", v & 0xFF))

    def u16(self, v: int):
        self.buf.write(struct.pack("<H", v & 0xFFFF))

    def i16(self, v: int):
        self.buf.write(struct.pack("<h", v))

    def u24(self, v: int):
        self.buf.write(struct.pack("B", v & 0xFF))
        self.buf.write(struct.pack("<H", (v >> 8) & 0xFFFF))

    def u32(self, v: int):
        self.buf.write(struct.pack("<I", v & 0xFFFFFFFF))

    def u32be(self, v: int):
        self.buf.write(struct.pack(">I", v & 0xFFFFFFFF))

    def write(self, data: bytes):
        self.buf.write(data)

    def getvalue(self) -> bytes:
        return self.buf.getvalue()

    def write_block_size(self, tag_high: int, size: int):
        """Write a tag byte with block size encoding."""
        if size <= 12:
            self.u8(tag_high | size)
        elif size <= 0xFF:
            self.u8(tag_high | 13)
            self.u8(size)
        elif size <= 0xFFFF:
            self.u8(tag_high | 14)
            self.u16(size)
        else:
            self.u8(tag_high | 15)
            self.u24(size)

    def write_short_size(self, size: int):
        """Write a short size value (used in command headers)."""
        if size < 0x80:
            self.u8(size)
        else:
            self.u8(((size >> 8) & 0x7F) | 0x80)
            self.u8(size & 0xFF)
