import struct


class Reader:
    """Utility class for reading binary data with a cursor position. Provides methods to read various integer sizes and blocks of bytes, as well as some custom size formats used in GCX files."""

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos

    def u8(self) -> int:
        v = self.data[self.pos]
        self.pos += 1
        return v

    def u8_at(self, offset: int) -> int:
        return self.data[offset]

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def i16(self) -> int:
        v = struct.unpack_from("<h", self.data, self.pos)[0]
        self.pos += 2
        return v

    def u24(self) -> int:
        b0 = self.data[self.pos]
        b12 = struct.unpack_from("<H", self.data, self.pos + 1)[0]
        self.pos += 3
        return b0 | (b12 << 8)

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def u32_at(self, offset: int) -> int:
        return struct.unpack_from("<I", self.data, offset)[0]

    def u32be(self) -> int:
        v = struct.unpack_from(">I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def read_bytes(self, n: int) -> bytes:
        v = self.data[self.pos : self.pos + n]
        self.pos += n
        return v

    def get_block_size(self) -> int:
        value = self.u8() & 0xF
        if value == 13:
            return self.u8()
        elif value == 14:
            return self.u16()
        elif value == 15:
            return self.u24()
        return value

    def get_short_size(self) -> int:
        value = self.u8()
        if (value & 0x80) == 0:
            return value
        else:
            value2 = self.u8()
            return ((value << 8) | value2) & 0x7FFF
