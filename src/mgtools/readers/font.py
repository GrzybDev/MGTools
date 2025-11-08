import os
import struct
import xml.etree.ElementTree as ET
from io import BufferedReader, BytesIO
from pathlib import Path

from PIL import Image

from mgtools.constants import EXPORT_FONT_ATLAS_EXTENSION, EXPORT_FONT_METADATA_FILENAME
from mgtools.dataclasses.glyph import Glyph
from mgtools.enumerators.data_type import DataType
from mgtools.file import File
from mgtools.mg1.constants import (
    FONT_EXPORT_ATLAS_HEIGHT,
    FONT_EXPORT_ATLAS_WIDTH,
    FONT_GLYPH_COUNT,
    FONT_GLYPH_HEIGHTS,
    FONT_MINIMUM_PAGE_SIZE,
    FONT_START_CHAR,
)
from mgtools.mgscii import get_mgscii_char


class Font(File):

    @property
    def raw_data(self) -> bytes:
        page_bytes = b""

        for page in self.__pages:
            glyphs_data = bytearray()
            bitmap_data = bytearray()

            for glyph in page:
                glyphs_data.extend(glyph.offset.to_bytes(2, "little"))

                if glyph.width == 1:
                    glyphs_data.extend((0).to_bytes(2))
                else:
                    glyphs_data.extend(((glyph.width - 1) << 4).to_bytes(2, "little"))

                if glyph.width != 1 and glyph.width != 4096 and glyph.image is not None:
                    packed_bitmap_data = Font.__pack_bitmap_data(glyph.image.tobytes())
                    bitmap_data.extend(packed_bitmap_data)

            missing_bytes = FONT_MINIMUM_PAGE_SIZE - len(glyphs_data + bitmap_data)
            bitmap_data.extend(b"\0" * missing_bytes)

            page_bytes += (
                len(glyphs_data + bitmap_data).to_bytes(4) + glyphs_data + bitmap_data
            )

        return (
            self.data_type.value.to_bytes(2)
            + b"\0\0"  # Identifier placeholder
            + page_bytes
        )

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__pages = []

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
    ) -> Font:
        data_type = DataType(int.from_bytes(reader.read(2)))

        if data_type != DataType.MG1_FONT:
            raise ValueError("Font files must have MG1_FONT data type.")

        reader.seek(2, os.SEEK_CUR)  # Skip identifier

        f = Font(data_type=data_type)

        for idx in range(5):
            page_size = int.from_bytes(reader.read(4))
            page_data = reader.read(page_size)
            f.add_data(page_data=BytesIO(page_data), page_index=idx)

        return f

    @staticmethod
    def from_file(file_path: Path) -> File:
        xmlroot = ET.parse(file_path / EXPORT_FONT_METADATA_FILENAME).getroot()
        page_elements = xmlroot.findall("Page")
        page_bytes = b""

        for page_idx, page in enumerate(page_elements):
            altas_path = file_path / f"{page_idx}.{EXPORT_FONT_ATLAS_EXTENSION}"

            glyphs_data = bytearray()
            bitmap_data = bytearray()

            if not altas_path.exists():
                page_glyphs_path = file_path / f"{page_idx}"

                for glyph_element in page.findall("Glyph"):
                    glyph_image_path = (
                        page_glyphs_path
                        / f"{int(glyph_element.get('index', '')):03d}.png"
                    )

                    if not glyph_image_path.exists():
                        width = int(glyph_element.get("width", "0"))
                        glyph_bitmap_data = b""
                    else:
                        glyph_image = Image.open(glyph_image_path).convert("L")
                        pixel_data = glyph_image.tobytes()

                        glyph_bitmap_data = Font.__pack_bitmap_data(pixel_data)

                        width = glyph_image.width

                    glyphs_data.extend(len(bitmap_data).to_bytes(2, "little"))

                    if width == 1:
                        glyphs_data.extend((0).to_bytes(2))
                    else:
                        glyphs_data.extend(((width - 1) << 4).to_bytes(2, "little"))

                    if width != 1 and width != 4096:
                        bitmap_data.extend(glyph_bitmap_data)
            else:
                atlas_image = Image.open(
                    file_path / f"{page_idx}.{EXPORT_FONT_ATLAS_EXTENSION}"
                ).convert("L")

                for glyph_element in page.findall("Glyph"):
                    width = int(glyph_element.get("width", "0"))

                    x_offset = int(glyph_element.get("x_offset", "0"))
                    y_offset = int(glyph_element.get("y_offset", "0"))

                    glyph_image = atlas_image.crop(
                        (
                            x_offset,
                            y_offset,
                            x_offset + width,
                            y_offset + FONT_GLYPH_HEIGHTS[page_idx],
                        )
                    )

                    pixel_data = glyph_image.tobytes()
                    glyph_bitmap_data = Font.__pack_bitmap_data(pixel_data)

                    glyphs_data.extend(len(bitmap_data).to_bytes(2, "little"))

                    if width == 1:
                        glyphs_data.extend((0).to_bytes(2))
                    else:
                        glyphs_data.extend(((width - 1) << 4).to_bytes(2, "little"))

                    if width != 1 and width != 4096:
                        bitmap_data.extend(glyph_bitmap_data)

            page_bytes += (
                len(glyphs_data + bitmap_data).to_bytes(4) + glyphs_data + bitmap_data
            )

        return Font.from_stream(
            BytesIO(DataType.MG1_FONT.value.to_bytes(2) + b"\0\0" + page_bytes)
        )

    def add_data(self, **kwargs) -> None:
        if "page_data" not in kwargs:
            raise ValueError("Missing 'page_data' argument.")

        page_index = kwargs.get("page_index", len(self.__pages))

        reader = kwargs["page_data"]
        glyphs: list[Glyph] = []

        for i in range(FONT_GLYPH_COUNT):
            offset, metrics = struct.unpack("<HH", reader.read(4))
            glyphs.append(
                Glyph(
                    char=get_mgscii_char(FONT_START_CHAR + i),
                    index=FONT_START_CHAR + i,
                    offset=offset,
                    width=(metrics >> 4) + 1,
                )
            )

        bitmap_data_offset_start = reader.tell()

        for glyph in glyphs:
            reader.seek(bitmap_data_offset_start + glyph.offset, os.SEEK_SET)
            bitmap_size = glyph.width * FONT_GLYPH_HEIGHTS[page_index]

            if glyph.width == 4096:
                continue

            unpacked_bitmap_data = self.__unpack_bitmap_data(
                glyph,
                reader.read(bitmap_size),
                FONT_GLYPH_HEIGHTS[page_index],
            )

            # Make sure the unpacked data length matches expected size
            if len(unpacked_bitmap_data) < glyph.width * FONT_GLYPH_HEIGHTS[page_index]:
                unpacked_bitmap_data += b"\0" * (
                    glyph.width * FONT_GLYPH_HEIGHTS[page_index]
                    - len(unpacked_bitmap_data)
                )

            image = Image.frombytes(
                "L",
                (glyph.width, FONT_GLYPH_HEIGHTS[page_index]),
                bytes(unpacked_bitmap_data),
                "raw",
            )

            glyph.image = image.point(lambda i: i * (255 // 3))

        self.__pages.append(glyphs)

    @staticmethod
    def __unpack_bitmap_data(glyph: Glyph, pixel_data: bytes, height: int) -> bytes:
        unpacked_bitmap_data = bytearray()

        for byte in pixel_data:
            p1 = (byte >> 6) & 0b11
            p2 = (byte >> 4) & 0b11
            p3 = (byte >> 2) & 0b11
            p4 = byte & 0b11

            unpacked_bitmap_data.append(p1)
            unpacked_bitmap_data.append(p2)
            unpacked_bitmap_data.append(p3)
            unpacked_bitmap_data.append(p4)

        return unpacked_bitmap_data

    @staticmethod
    def __pack_bitmap_data(pixel_bytes: bytes) -> bytes:
        packed_bitmap_data = bytearray()

        try:
            for i in range(0, len(pixel_bytes), 4):
                p1 = pixel_bytes[i] & 0b11
                p2 = pixel_bytes[i + 1] & 0b11
                p3 = pixel_bytes[i + 2] & 0b11
                p4 = pixel_bytes[i + 3] & 0b11

                packed_byte = (p1 << 6) | (p2 << 4) | (p3 << 2) | p4
                packed_bitmap_data.append(packed_byte)
        except IndexError:
            pass

        return bytes(packed_bitmap_data)

    def __generate_atlas(self, output_path: Path, page_index: int) -> None:
        glyphs = self.__pages[page_index]
        atlas_image = Image.new(
            "L", (FONT_EXPORT_ATLAS_WIDTH, FONT_EXPORT_ATLAS_HEIGHT)
        )

        x_offset = 0
        y_offset = 0

        for glyph in glyphs:
            if glyph.image is None:
                continue

            if x_offset + glyph.width > FONT_EXPORT_ATLAS_WIDTH:
                x_offset = 0
                y_offset += FONT_GLYPH_HEIGHTS[page_index]

            atlas_image.paste(glyph.image, (x_offset, y_offset))

            glyph.x_offset = x_offset
            glyph.y_offset = y_offset

            if glyph.width == 1:
                continue

            x_offset += glyph.width

        atlas_image.save(output_path)

    def __generate_glyph_images(self, output_path: Path, page_index: int) -> None:
        glyphs = self.__pages[page_index]
        output_path.mkdir(parents=True, exist_ok=True)

        for glyph in glyphs:
            if glyph.image is None:
                continue

            glyph_image_path = output_path / f"{glyph.index:03d}.png"
            glyph.image.save(glyph_image_path)

    def __generate_metadata(self, output_path: Path) -> None:
        root = ET.Element("Font")

        for page_index, glyphs in enumerate(self.__pages):
            page_element = ET.SubElement(root, "Page", index=str(page_index))

            for glyph in glyphs:
                ET.SubElement(
                    page_element,
                    "Glyph",
                    index=str(glyph.index),
                    char=repr(str(glyph.char))[1:-1],
                    width=str(glyph.width),
                    x_offset=str(glyph.x_offset),
                    y_offset=str(glyph.y_offset),
                )

        tree = ET.ElementTree(root)
        ET.indent(tree)
        tree.write(
            output_path / EXPORT_FONT_METADATA_FILENAME,
            encoding="utf-8",
            xml_declaration=True,
        )

    def export(self, output_path: Path, **kwargs) -> None:
        for page_index in range(len(self.__pages)):
            if kwargs.get("separate_chars", False):
                self.__generate_glyph_images(
                    output_path / f"{page_index}",
                    page_index,
                )
            else:
                self.__generate_atlas(
                    output_path / f"{page_index}.{EXPORT_FONT_ATLAS_EXTENSION}",
                    page_index,
                )

            self.__generate_metadata(
                output_path,
            )
