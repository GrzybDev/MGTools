import math
import os
import struct
import xml.etree.ElementTree as ET
from io import BufferedReader, BytesIO
from pathlib import Path

from PIL import Image

from mgtools.constants import (
    EXPORT_FONT_ATLAS_EXTENSION,
    EXPORT_FONT_METADATA_FILENAME,
)
from mgtools.dataclasses.glyph import Glyph
from mgtools.enumerators.data_type import DataType
from mgtools.mg1.constants import (
    FONT_EXPORT_ATLAS_HEIGHT,
    FONT_EXPORT_ATLAS_WIDTH,
    FONT_GLYPH_COUNT,
    FONT_GLYPH_HEIGHTS,
    FONT_MINIMUM_PAGE_SIZE,
    FONT_START_CHAR,
)
from mgtools.resource.asset import Asset
from mgtools.utilities.mgscii import get_mgscii_char


class Font(Asset):
    @property
    def raw_data(self) -> bytes:
        page_bytes = b""

        for page_idx, page in enumerate(self.__pages):
            glyphs_data = bytearray()
            glyph_header_size = FONT_GLYPH_COUNT * 4

            # Determine bitmap area size
            if page_idx in self.__page_bitmap_sizes:
                bitmap_total = self.__page_bitmap_sizes[page_idx]
            else:
                # Fallback: compute from packed data
                bitmap_total = sum(
                    len(Font.__pack_bitmap_data(g.image.tobytes()))
                    for g in page
                    if g.width != 1 and g.width != 4096 and g.image is not None
                )

            target_page_size = max(
                FONT_MINIMUM_PAGE_SIZE, glyph_header_size + bitmap_total
            )
            bitmap_area_size = target_page_size - glyph_header_size
            bitmap_data = bytearray(bitmap_area_size)

            for glyph in page:
                glyphs_data.extend(glyph.offset.to_bytes(2, "little"))

                if glyph.width == 1:
                    glyphs_data.extend((0).to_bytes(2))
                else:
                    glyphs_data.extend(((glyph.width - 1) << 4).to_bytes(2, "little"))

                if glyph.width != 1 and glyph.width != 4096 and glyph.image is not None:
                    packed_bitmap_data = Font.__pack_bitmap_data(glyph.image.tobytes())
                    # Apply phantom pixel pad bits to last byte
                    if glyph.pad_bits and len(packed_bitmap_data) > 0:
                        packed_bitmap_data = packed_bitmap_data[:-1] + bytes(
                            [packed_bitmap_data[-1] | glyph.pad_bits]
                        )
                    # Write at the glyph's original offset position
                    end = glyph.offset + len(packed_bitmap_data)
                    if end <= len(bitmap_data):
                        bitmap_data[glyph.offset : end] = packed_bitmap_data
                    # Write tail data (non-zero trailing bytes past image boundary)
                    if glyph.tail_data:
                        tail_start = glyph.offset + len(packed_bitmap_data)
                        tail_end = tail_start + len(glyph.tail_data)
                        if tail_end <= len(bitmap_data):
                            bitmap_data[tail_start:tail_end] = glyph.tail_data

            page_data = glyphs_data + bitmap_data
            page_bytes += len(page_data).to_bytes(4) + page_data

        return self.data_type.to_bytes(2) + self.__identifier + page_bytes

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__pages = []
        self.__identifier = b"\0\0"
        self.__page_bitmap_sizes: dict[int, int] = {}

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
        data_type: DataType | None = None,
    ) -> Asset:
        if data_type is None:
            data_type = DataType(int.from_bytes(reader.read(2)))

        if data_type != DataType.MG1_FONT:
            raise ValueError("Font files must have MG1_FONT data type.")

        f = Font(data_type=data_type)
        f.__identifier = reader.read(2)

        for idx in range(5):
            page_size = int.from_bytes(reader.read(4))
            page_data = reader.read(page_size)
            f.add_data(
                page_data=BytesIO(page_data), page_index=idx, page_size=page_size
            )

        return f

    @staticmethod
    def __encode_glyph(
        width: int,
        bitmap_bytes: bytes,
        glyphs_data: bytearray,
        bitmap_data: bytearray,
    ) -> None:
        """Append one glyph's header + bitmap to the accumulators."""
        glyphs_data.extend(len(bitmap_data).to_bytes(2, "little"))
        glyphs_data.extend(
            (0).to_bytes(2) if width == 1 else ((width - 1) << 4).to_bytes(2, "little")
        )

        if width != 1 and width != 4096:
            bitmap_data.extend(bitmap_bytes)

    @staticmethod
    def from_file(
        file_path: Path, data_type: DataType | None = None, **kwargs
    ) -> Asset:
        identifier = kwargs.get("identifier", b"\0\0")
        xmlroot = ET.parse(file_path / EXPORT_FONT_METADATA_FILENAME).getroot()
        page_elements = xmlroot.findall("Page")
        page_bytes = b""

        for page_idx, page in enumerate(page_elements):
            bitmap_data_size_str = page.get("bitmap_data_size")
            has_positioning = bitmap_data_size_str is not None
            atlas_path = file_path / f"{page_idx}.{EXPORT_FONT_ATLAS_EXTENSION}"

            glyph_elements = page.findall("Glyph")

            if has_positioning:
                # Use stored positioning for lossless round-trip
                bitmap_data_size = int(bitmap_data_size_str)
                glyph_header_size = FONT_GLYPH_COUNT * 4
                target_page_size = max(
                    FONT_MINIMUM_PAGE_SIZE, glyph_header_size + bitmap_data_size
                )
                bitmap_area_size = target_page_size - glyph_header_size
                glyphs_data = bytearray()
                bitmap_data = bytearray(bitmap_area_size)

                # Load images from atlas or individual files
                atlas_image = None
                page_glyphs_path = file_path / f"{page_idx}"
                if atlas_path.exists():
                    atlas_image = Image.open(atlas_path).convert("L")

                for glyph_element in glyph_elements:
                    width = int(glyph_element.get("width", "0"))
                    data_offset = int(glyph_element.get("data_offset", "0"))

                    glyphs_data.extend(data_offset.to_bytes(2, "little"))
                    if width == 1:
                        glyphs_data.extend((0).to_bytes(2))
                    else:
                        glyphs_data.extend(((width - 1) << 4).to_bytes(2, "little"))

                    if width == 1 or width == 4096:
                        continue

                    # Get glyph image
                    glyph_bitmap_data = b""
                    if atlas_image is not None:
                        x_off = int(glyph_element.get("x_offset", "0"))
                        y_off = int(glyph_element.get("y_offset", "0"))
                        glyph_image = atlas_image.crop(
                            (
                                x_off,
                                y_off,
                                x_off + width,
                                y_off + FONT_GLYPH_HEIGHTS[page_idx],
                            )
                        )
                        glyph_bitmap_data = Font.__pack_bitmap_data(
                            glyph_image.tobytes()
                        )
                    else:
                        glyph_idx = int(glyph_element.get("index", "0"))
                        glyph_image_path = page_glyphs_path / f"{glyph_idx:03d}.png"
                        if glyph_image_path.exists():
                            glyph_image = Image.open(glyph_image_path).convert("L")
                            glyph_bitmap_data = Font.__pack_bitmap_data(
                                glyph_image.tobytes()
                            )

                    # Apply phantom pixel pad bits to last byte
                    pad_bits_hex = glyph_element.get("pad_bits")
                    if pad_bits_hex and len(glyph_bitmap_data) > 0:
                        pad = int(pad_bits_hex, 16)
                        glyph_bitmap_data = glyph_bitmap_data[:-1] + bytes(
                            [glyph_bitmap_data[-1] | pad]
                        )

                    # Write at original offset position
                    end = data_offset + len(glyph_bitmap_data)
                    if end <= len(bitmap_data):
                        bitmap_data[data_offset:end] = glyph_bitmap_data
                    # Write tail data (non-zero trailing bytes past image boundary)
                    tail_hex = glyph_element.get("tail_data")
                    if tail_hex:
                        tail_bytes = bytes.fromhex(tail_hex)
                        tail_start = data_offset + len(glyph_bitmap_data)
                        tail_end = tail_start + len(tail_bytes)
                        if tail_end <= len(bitmap_data):
                            bitmap_data[tail_start:tail_end] = tail_bytes

                page_data = glyphs_data + bitmap_data
                page_bytes += len(page_data).to_bytes(4) + page_data

            else:
                # Fallback: sequential layout (no stored positioning)
                glyphs_data = bytearray()
                bitmap_data = bytearray()

                if not atlas_path.exists():
                    page_glyphs_path = file_path / f"{page_idx}"

                    for glyph_element in glyph_elements:
                        glyph_image_path = (
                            page_glyphs_path
                            / f"{int(glyph_element.get('index', '')):03d}.png"
                        )

                        if not glyph_image_path.exists():
                            width = int(glyph_element.get("width", "0"))
                            glyph_bitmap_data = b""
                        else:
                            glyph_image = Image.open(glyph_image_path).convert("L")
                            glyph_bitmap_data = Font.__pack_bitmap_data(
                                glyph_image.tobytes()
                            )
                            width = glyph_image.width

                        Font.__encode_glyph(
                            width, glyph_bitmap_data, glyphs_data, bitmap_data
                        )
                else:
                    atlas_image = Image.open(atlas_path).convert("L")

                    for glyph_element in glyph_elements:
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

                        glyph_bitmap_data = Font.__pack_bitmap_data(
                            glyph_image.tobytes()
                        )

                        Font.__encode_glyph(
                            width, glyph_bitmap_data, glyphs_data, bitmap_data
                        )

                page_bytes += (
                    len(glyphs_data + bitmap_data).to_bytes(4)
                    + glyphs_data
                    + bitmap_data
                )

        return Font.from_stream(
            BytesIO(DataType.MG1_FONT.to_bytes(2) + identifier + page_bytes)
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
        page_data_size = kwargs.get("page_size", 0)
        bitmap_data_total = page_data_size - bitmap_data_offset_start
        self.__page_bitmap_sizes[page_index] = bitmap_data_total

        # Compute per-glyph packed_size from offset table
        real_glyphs = [
            (i, g) for i, g in enumerate(glyphs) if g.width != 1 and g.width != 4096
        ]
        sorted_real = sorted(real_glyphs, key=lambda x: x[1].offset)
        for ri, (gi, glyph) in enumerate(sorted_real):
            if ri + 1 < len(sorted_real):
                glyph.packed_size = sorted_real[ri + 1][1].offset - glyph.offset
            else:
                glyph.packed_size = bitmap_data_total - glyph.offset

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

            # Capture tail bytes (packed data past the image boundary)
            image_packed_size = math.ceil(
                glyph.width * FONT_GLYPH_HEIGHTS[page_index] / 4
            )
            if glyph.packed_size > image_packed_size:
                reader.seek(
                    bitmap_data_offset_start + glyph.offset + image_packed_size,
                    os.SEEK_SET,
                )
                tail = reader.read(glyph.packed_size - image_packed_size)
                if any(b != 0 for b in tail):
                    glyph.tail_data = tail

            # Capture phantom pixel bits in the last packed byte
            pixel_count = glyph.width * FONT_GLYPH_HEIGHTS[page_index]
            remainder = pixel_count % 4
            if remainder != 0 and image_packed_size > 0:
                last_byte_pos = (
                    bitmap_data_offset_start + glyph.offset + image_packed_size - 1
                )
                reader.seek(last_byte_pos, os.SEEK_SET)
                last_byte = reader.read(1)[0]
                phantom_mask = (1 << (2 * (4 - remainder))) - 1
                pad = last_byte & phantom_mask
                if pad != 0:
                    glyph.pad_bits = pad

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
        length = len(pixel_bytes)

        for i in range(0, length, 4):
            p1 = pixel_bytes[i] & 0b11 if i < length else 0
            p2 = pixel_bytes[i + 1] & 0b11 if i + 1 < length else 0
            p3 = pixel_bytes[i + 2] & 0b11 if i + 2 < length else 0
            p4 = pixel_bytes[i + 3] & 0b11 if i + 3 < length else 0

            packed_byte = (p1 << 6) | (p2 << 4) | (p3 << 2) | p4
            packed_bitmap_data.append(packed_byte)

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
            page_attrs = {"index": str(page_index)}
            if page_index in self.__page_bitmap_sizes:
                page_attrs["bitmap_data_size"] = str(
                    self.__page_bitmap_sizes[page_index]
                )
            page_element = ET.SubElement(root, "Page", page_attrs)

            for glyph in glyphs:
                attrs = {
                    "index": str(glyph.index),
                    "char": repr(str(glyph.char))[1:-1],
                    "width": str(glyph.width),
                    "x_offset": str(glyph.x_offset),
                    "y_offset": str(glyph.y_offset),
                }
                if glyph.packed_size > 0:
                    attrs["packed_size"] = str(glyph.packed_size)
                if glyph.tail_data:
                    attrs["tail_data"] = glyph.tail_data.hex()
                if glyph.pad_bits:
                    attrs["pad_bits"] = format(glyph.pad_bits, "02x")
                attrs["data_offset"] = str(glyph.offset)
                ET.SubElement(page_element, "Glyph", attrs)

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
