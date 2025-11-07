import os
import struct
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

from PIL import Image

from mgtools.file import File
from mgtools.mg1.chunks.font import Font as FontChunk
from mgtools.mg1.constants import (
    FONT_EXPORT_ATLAS_HEIGHT,
    FONT_EXPORT_ATLAS_WIDTH,
    FONT_GLYPH_COUNT,
    FONT_GLYPH_HEIGHTS,
    FONT_START_CHAR,
)
from mgtools.mg1.dataclasses.glyph import Glyph


class Font(File):

    def __init__(self, chunk: FontChunk) -> None:
        self.__pages = [
            self.__parse_page(chunk.get_page(i), FONT_GLYPH_HEIGHTS[i])
            for i in range(chunk.page_count)
        ]

    def __parse_page(self, page_bytes: BytesIO, glyph_height: int) -> list[Glyph]:
        glyphs: list[Glyph] = []

        for i in range(FONT_GLYPH_COUNT):
            offset, metrics = struct.unpack("<HH", page_bytes.read(4))
            glyph = Glyph(
                char=chr(i + FONT_START_CHAR), offset=offset, width=(metrics >> 4) + 1
            )
            glyphs.append(glyph)

        bitmap_data_start_offset = page_bytes.tell()

        for glyph in glyphs:
            page_bytes.seek(bitmap_data_start_offset + glyph.offset, os.SEEK_SET)
            bitmap_size = glyph.width * glyph_height

            if glyph.width == 4096:
                continue

            glyph_bitmap = self.__generate_glyph_image(
                glyph, page_bytes.read(bitmap_size), glyph_height
            )
            glyph.image = glyph_bitmap

        return glyphs

    def __generate_glyph_image(
        self, glyph: Glyph, bitmap_data: bytes, glyph_height: int
    ) -> Image.Image:
        unpacked_bitmap_data = bytearray()

        # 2bpp to 8bpp
        for byte in bitmap_data:
            # Extract 2-bit values from the current byte (MSB first)
            p1 = (byte >> 6) & 0b11  # Top-left 2 bits
            p2 = (byte >> 4) & 0b11
            p3 = (byte >> 2) & 0b11
            p4 = byte & 0b11  # Bottom-right 2 bits

            # Append the four extracted 8-bit pixels (values 0-3)
            unpacked_bitmap_data.append(p1)
            unpacked_bitmap_data.append(p2)
            unpacked_bitmap_data.append(p3)
            unpacked_bitmap_data.append(p4)

        # Create a new grayscale image
        image = Image.frombytes(
            "L",
            (glyph.width, glyph_height),
            bytes(unpacked_bitmap_data),
            "raw",
        )
        return image.point(lambda i: i * (255 // 3))

    def __write_metadata(self, path: Path) -> None:
        root = ET.Element("Font")

        for page_index, page in enumerate(self.__pages):
            page_element = ET.SubElement(
                root, "Page", attrib={"index": str(page_index)}
            )

            for glyph in page:
                glyph_attrib = {
                    "index": str(ord(glyph.char) - 30),
                    "char": repr(str(glyph.char))[1:-1],
                    "width": str(glyph.width),
                    "x_offset": str(glyph.x_offset),
                    "y_offset": str(glyph.y_offset),
                }
                ET.SubElement(page_element, "Glyph", attrib=glyph_attrib)

        tree = ET.ElementTree(root)
        ET.indent(tree)
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def __write_bitmap(self, path: Path, page_index: int) -> None:
        page = self.__pages[page_index]
        atlas_image = Image.new(
            "L", (FONT_EXPORT_ATLAS_WIDTH, FONT_EXPORT_ATLAS_HEIGHT)
        )

        x_offset = 0
        y_offset = 0
        for glyph in page:
            if glyph.image is None:
                continue

            if x_offset + glyph.width > FONT_EXPORT_ATLAS_WIDTH:
                x_offset = 0
                y_offset += FONT_GLYPH_HEIGHTS[page_index]

            atlas_image.paste(glyph.image, (x_offset, y_offset))
            glyph.x_offset = x_offset
            glyph.y_offset = y_offset

            x_offset += glyph.width

        atlas_image.save(path)

    def save(self, path: Path, separate_chars: bool = False) -> None:
        for page_index in range(len(self.__pages)):
            if separate_chars:
                page = self.__pages[page_index]
                page_dir = path / f"page_{page_index}"
                page_dir.mkdir(parents=True, exist_ok=True)

                for glyph in page:
                    if glyph.image is None:
                        continue

                    glyph.image.save(page_dir / f"char_{ord(glyph.char) - 30:03d}.png")
            else:
                self.__write_bitmap(path / f"page_{page_index}.png", page_index)

        self.__write_metadata(path / "characters.xml")
