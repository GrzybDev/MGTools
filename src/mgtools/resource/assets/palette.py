import struct
import xml.etree.ElementTree as ET
from io import BufferedReader, BytesIO
from pathlib import Path

from mgtools.enumerators.data_type import DataType
from mgtools.resource.asset import Asset


class Palette(Asset):
    @property
    def raw_data(self) -> bytes:
        if self.data_type == DataType.MG2_SECTION:
            raw_bytes = b""

            for block in self.__color_blocks:
                block_data = b""
                for r, g, b in block:
                    block_data += struct.pack("BBBB", b, g, r, 0)
                raw_bytes += len(block_data).to_bytes(4) + block_data

            return raw_bytes

        raw_bytes = self.data_type.to_bytes(2)

        palette_data = b""
        palette_data += (len(self.__colors) * 4).to_bytes(4)

        for r, g, b in self.__colors:
            palette_data += struct.pack("BBBB", b, g, r, 0)

        raw_bytes += len(palette_data).to_bytes(2) + palette_data
        return raw_bytes

    @property
    def palette_bytes(self) -> bytes:
        palette = b""

        for r, g, b in self.__colors[:256]:
            palette += bytes([r, g, b])

        return palette

    @property
    def block_count(self) -> int:
        return len(self.__color_blocks)

    def get_block_size(self, block_index: int) -> int:
        return len(self.__color_blocks[block_index])

    def build_palette_bytes(self, block_offsets: list[tuple[int, int]]) -> bytes:
        """Build a 256-color RGB palette from specific blocks at given offsets.

        Args:
            block_offsets: List of (block_index, start_offset) pairs.
                Each block's colors are placed starting at start_offset
                in the 256-entry palette.

        Returns:
            768 bytes of RGB palette data (256 * 3).
        """
        palette: list[tuple[int, int, int]] = [(0, 0, 0)] * 256

        for block_index, start_offset in block_offsets:
            for i, color in enumerate(self.__color_blocks[block_index]):
                idx = start_offset + i
                if 0 <= idx < 256:
                    palette[idx] = color

        result = b""
        for r, g, b in palette:
            result += bytes([r, g, b])
        return result

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__colors: list[tuple[int, int, int]] = []
        self.__color_blocks: list[list[tuple[int, int, int]]] = []

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
        data_type: DataType | None = None,
    ) -> Asset:
        if data_type is None:
            data_type = DataType(int.from_bytes(reader.read(2)))

            if data_type != DataType.MG1_SECTION:
                raise ValueError("Palette files must have MG1_SECTION data type.")

        if data_type == DataType.MG2_SECTION:
            f = Palette(data_type=data_type)

            while True:
                raw_size = reader.read(4)
                if len(raw_size) < 4:
                    break

                block_size = int.from_bytes(raw_size)
                if block_size == 0:
                    break

                block_data = reader.read(block_size)
                block_colors: list[tuple[int, int, int]] = []

                for i in range(0, len(block_data), 4):
                    b, g, r, _ = struct.unpack("BBBB", block_data[i : i + 4])
                    f.add_data(r=r, g=g, b=b)
                    block_colors.append((r, g, b))

                f.__color_blocks.append(block_colors)

            return f

        data_length = int.from_bytes(reader.read(2))

        palette_data = BytesIO(reader.read(data_length))

        f = Palette(data_type=data_type)

        colors_count = int.from_bytes(palette_data.read(4)) // 4

        for _ in range(colors_count):
            b, g, r, _ = struct.unpack("BBBB", palette_data.read(4))
            f.add_data(r=r, g=g, b=b)

        return f

    @staticmethod
    def from_file(file_path: Path, data_type: DataType | None = None) -> Asset:
        xmlroot = ET.parse(file_path).getroot()

        f = Palette(data_type=data_type or DataType.MG1_SECTION)

        if data_type == DataType.MG2_SECTION:
            # MG2: read block structure from XML
            block_elements = xmlroot.findall("Block")
            if block_elements:
                for block_elem in block_elements:
                    block_colors: list[tuple[int, int, int]] = []
                    for color_elem in block_elem.findall("Color"):
                        r = int(color_elem.get("r", "0"))
                        g = int(color_elem.get("g", "0"))
                        b = int(color_elem.get("b", "0"))
                        f.add_data(r=r, g=g, b=b)
                        block_colors.append((r, g, b))
                    f.__color_blocks.append(block_colors)
            else:
                # Fallback: flat color list, put all in one block
                block_colors = []
                for color_elem in xmlroot.findall("Color"):
                    r = int(color_elem.get("r", "0"))
                    g = int(color_elem.get("g", "0"))
                    b = int(color_elem.get("b", "0"))
                    f.add_data(r=r, g=g, b=b)
                    block_colors.append((r, g, b))
                f.__color_blocks.append(block_colors)
        else:
            for color_elem in xmlroot.findall("Color"):
                r = int(color_elem.get("r", "0"))
                g = int(color_elem.get("g", "0"))
                b = int(color_elem.get("b", "0"))
                f.add_data(r=r, g=g, b=b)

        return f

    def add_data(self, **kwargs) -> None:
        self.__colors.append(
            (
                kwargs.get("r", 0),
                kwargs.get("g", 0),
                kwargs.get("b", 0),
            )
        )

    def export(self, output_path: Path, **kwargs) -> None:
        root = ET.Element("Palette")

        if self.data_type == DataType.MG2_SECTION and self.__color_blocks:
            # MG2: preserve block structure
            global_index = 0
            for block_idx, block in enumerate(self.__color_blocks):
                block_elem = ET.SubElement(
                    root, "Block", attrib={"index": str(block_idx)}
                )
                for r, g, b in block:
                    ET.SubElement(
                        block_elem,
                        "Color",
                        attrib={
                            "index": str(global_index),
                            "r": str(r),
                            "g": str(g),
                            "b": str(b),
                        },
                    )
                    global_index += 1
        else:
            for i, (r, g, b) in enumerate(self.__colors):
                ET.SubElement(
                    root,
                    "Color",
                    attrib={
                        "index": str(i),
                        "r": str(r),
                        "g": str(g),
                        "b": str(b),
                    },
                )

        tree = ET.ElementTree(root)
        ET.indent(tree)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
