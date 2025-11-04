import os
import struct
from io import BytesIO

from mgtools.mg1.chunks.single import SingleChunk


class Palette:

    __header_bytes = b""

    @property
    def color_map(self) -> bytes:
        color_map = b""

        for r, g, b in self.__colors:
            color_map += bytes([b, g, r])

        return color_map

    def __init__(self, chunk: SingleChunk) -> None:
        self.__colors = []

        self.__parse_data(chunk.data)

    def __str__(self) -> str:
        return f"Palette(colors_count={len(self.__colors)}, header_bytes={self.__header_bytes})"

    def __parse_data(self, data: BytesIO) -> None:
        self.__colors.clear()

        self.__header_bytes = data.read(4)

        for _ in range(164):
            try:
                b, g, r, _ = struct.unpack("BBBB", data.read(4))
                self.__colors.append((b, g, r))
            except struct.error:
                break
