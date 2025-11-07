import os
import struct
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

from mgtools.file import File
from mgtools.mg1.chunks.single import Single


class Palette(File):

    @property
    def color_map(self) -> bytes:
        color_map = b""

        for r, g, b in self.__colors:
            color_map += bytes([b, g, r])

        return color_map

    def __init__(self, chunk: Single) -> None:
        self.__colors = []

        self.__parse_data(chunk.data)

    def __str__(self) -> str:
        return f"Palette(colors_count={len(self.__colors)})"

    def __parse_data(self, data: BytesIO) -> None:
        self.__colors.clear()

        colors_count = int.from_bytes(data.read(4)) // 4

        for _ in range(colors_count):
            b, g, r, _ = struct.unpack("BBBB", data.read(4))
            self.__colors.append((b, g, r))

    def save(self, path: Path) -> None:
        # Save palette as a XML file
        root = ET.Element("Palette")

        for index, (b, g, r) in enumerate(self.__colors):
            color_element = ET.SubElement(
                root,
                "Color",
                attrib={
                    "index": str(index),
                    "r": str(r),
                    "g": str(g),
                    "b": str(b),
                },
            )

        tree = ET.ElementTree(root)
        ET.indent(tree)
        tree.write(path, encoding="utf-8", xml_declaration=True)
