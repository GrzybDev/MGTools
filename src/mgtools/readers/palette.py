import struct
import xml.etree.ElementTree as ET
from io import BufferedReader, BytesIO
from pathlib import Path

from mgtools.enumerators.data_type import DataType
from mgtools.file import File


class Palette(File):

    @property
    def raw_data(self) -> bytes:
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

        for r, g, b in self.__colors:
            palette += bytes([r, g, b])

        return palette

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__colors: list[tuple[int, int, int]] = []

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
    ) -> Palette:
        data_type = DataType(int.from_bytes(reader.read(2)))

        if data_type != DataType.SIMPLE:
            raise ValueError("Palette files must have SIMPLE data type.")

        data_length = int.from_bytes(reader.read(2))

        palette_data = BytesIO(reader.read(data_length))

        f = Palette(data_type=data_type)

        colors_count = int.from_bytes(palette_data.read(4)) // 4

        for _ in range(colors_count):
            b, g, r, _ = struct.unpack("BBBB", palette_data.read(4))
            f.add_data(r=r, g=g, b=b)

        return f

    @staticmethod
    def from_file(file_path: Path) -> Palette:
        xmlroot = ET.parse(file_path).getroot()

        f = Palette(data_type=DataType.SIMPLE)

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
