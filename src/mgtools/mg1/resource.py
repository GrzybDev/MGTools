import os
import xml.etree.ElementTree as ET
from email.mime import base
from io import BufferedReader, BufferedWriter, BytesIO
from pathlib import Path
from tkinter import E, font

import polib
from PIL import Image

from mgtools.file import File
from mgtools.mg1.chunks.animated_sprite import AnimatedSprite
from mgtools.mg1.chunks.font import Font as FontChunk
from mgtools.mg1.chunks.single import Single
from mgtools.mg1.chunks.texture import Texture
from mgtools.mg1.constants import (
    EXPORT_FONT_FOLDER,
    EXPORT_LOCALE_EXTENSION,
    EXPORT_LOCALE_FOLDER,
    EXPORT_LOCALE_SCRIPTS_FOLDER,
    EXPORT_PALETTE_EXTENSION,
    EXPORT_PALETTE_FOLDER,
    EXPORT_SPRITE_EXTENSION,
    EXPORT_SPRITE_FOLDER,
    EXPORT_UNKNOWN_EXTENSION,
    EXPORT_UNKNOWN_FOLDER,
    FONT_EXPORT_ATLAS_WIDTH,
    FONT_GLYPH_HEIGHTS,
    RESOURCE_MAGIC,
)
from mgtools.mg1.enumerators.chunk_type import ChunkType
from mgtools.mg1.enumerators.file_type import FileType
from mgtools.mg1.enumerators.resource_platform import ResourcePlatform
from mgtools.mg1.formats.font import Font
from mgtools.mg1.formats.locale import Locale
from mgtools.mg1.formats.palette import Palette
from mgtools.mg1.formats.sprite import Sprite
from mgtools.mg1.formats.unknown import Unknown
from mgtools.mg1.mappings import (
    CHUNK_TYPE_OVERRIDES,
    FILE_NAME_MAP,
    FILE_TYPE_MAP,
    TEXT_BLOCKS,
    TEXT_BLOCKS_NAMES,
)


class Resource:

    @property
    def file_count(self) -> int:
        return len(self.__files)

    def __init__(self) -> None:
        self.__platform = ResourcePlatform.UNKNOWN
        self.__files = []

    def __str__(self) -> str:
        return (
            f"Resource(platform={self.__platform.name}, files_count={self.file_count})"
        )

    def load(self, reader: BufferedReader) -> None:
        magic = reader.read(2)

        if magic != RESOURCE_MAGIC:
            raise ValueError("Invalid resource file magic.")

        # No idea what those two bytes mean, so I am just using them to identify which resource file we're reading.
        platform_int = int.from_bytes(reader.read(2))

        try:
            self.__platform = ResourcePlatform(platform_int)
        except ValueError:
            self.__platform = ResourcePlatform.UNKNOWN

        self.__load_files(reader)

    def __load_files(self, reader: BufferedReader) -> None:
        while True:
            file_type_int = int.from_bytes(reader.read(2))

            if file_type_int == 0:
                break

            chunk_type = ChunkType(file_type_int)

            match chunk_type:
                case ChunkType.SINGLE:
                    file = self.__read_chunk(reader)
                    self.__files.append(file)
                case ChunkType.ANIMATED_SPRITE:
                    anim = self.__read_animated_sprite_chunk(reader)
                    self.__files.append(anim)
                case ChunkType.FONT:
                    font = self.__read_font_chunk(reader)
                    self.__files.append(font)
                case ChunkType.TEXTURE:
                    texture = self.__read_texture_chunk(reader)
                    self.__files.append(texture)

    def __read_chunk(self, reader: BufferedReader) -> Single:
        file_size = int.from_bytes(reader.read(2))
        file_data = reader.read(file_size)

        return Single(file_data)

    def __read_animated_sprite_chunk(self, reader: BufferedReader) -> AnimatedSprite:
        anim = AnimatedSprite()
        frame_count = int.from_bytes(reader.read(2)) // 2

        for _ in range(frame_count):
            frame_file_size = int.from_bytes(reader.read(4))
            frame_data = reader.read(frame_file_size)
            anim.add_frame(Single(frame_data))

        reader.seek(4, os.SEEK_CUR)  # Skip padding/alignment bytes
        return anim

    def __read_font_chunk(self, reader: BufferedReader) -> FontChunk:
        font = FontChunk(reader.read(2))

        for _ in range(5):  # Figure out where this 5 comes from
            page_size = int.from_bytes(reader.read(4))
            page_data = reader.read(page_size)
            font.add_page(page_data)

        return font

    def __read_texture_chunk(self, reader: BufferedReader) -> Texture:
        header_data = reader.read(2)
        texture = Texture(header_data)

        for _ in range(2):  # Figure out where this 2 comes from
            texture_size = int.from_bytes(reader.read(4))
            texture_data = reader.read(texture_size)
            texture.add_texture(texture_data)

        return texture

    def get_palette(self, palette_id: int | None = None) -> Palette:
        palette_files = [
            self.__files[i]
            for i in range(len(self.__files))
            if FILE_TYPE_MAP.get(i) == FileType.PALETTE
        ]

        if len(palette_files) == 0:
            raise ValueError("No palettes found in resource file.")

        if palette_id is not None:
            if palette_id < 0 or palette_id >= len(palette_files):
                raise ValueError(f"Palette ID {palette_id} is out of range.")
            return Palette(palette_files[palette_id])

        return Palette(palette_files[0])

    def __get_sprite(self, index: int) -> Sprite:
        if FILE_TYPE_MAP.get(index) != FileType.SPRITE:
            raise ValueError(f"File at index {index} is not a sprite.")

        return Sprite(self.__files[index])

    def get(self, index: int) -> File:
        file_type = FILE_TYPE_MAP.get(index, FileType.UNKNOWN)

        match file_type:
            case FileType.SPRITE:
                return self.__get_sprite(index)
            case FileType.PALETTE:
                return Palette(self.__files[index])
            case FileType.LOCALE:
                return Locale(self.__files[index])
            case FileType.FONT:
                return Font(self.__files[index])
            case _:
                return Unknown(self.__files[index])

    def __read_unknown_from_file(self, chunk_type: ChunkType, file_path: Path):
        with file_path.open("rb") as f:
            match chunk_type:
                case ChunkType.SINGLE:
                    file_data = f.read()
                    return Single(file_data)
                case ChunkType.ANIMATED_SPRITE:
                    anim = AnimatedSprite()
                    frame_count = int.from_bytes(f.read(2)) // 2

                    for _ in range(frame_count):
                        frame_file_size = int.from_bytes(f.read(4))
                        frame_data = f.read(frame_file_size)
                        anim.add_frame(Single(frame_data))

                    return anim
                case ChunkType.FONT:
                    header_data = f.read(2)
                    font = FontChunk(header_data)

                    for _ in range(5):  # Figure out where this 5 comes from
                        page_size_bytes = f.read(4)
                        if len(page_size_bytes) < 4:
                            break
                        page_size = int.from_bytes(page_size_bytes)
                        page_data = f.read(page_size)
                        font.add_page(page_data)

                    return font
                case ChunkType.TEXTURE:
                    header_data = f.read(2)
                    texture = Texture(header_data)

                    for _ in range(2):  # Figure out where this 2 comes from
                        texture_size_bytes = f.read(4)
                        if len(texture_size_bytes) < 4:
                            break
                        texture_size = int.from_bytes(texture_size_bytes)
                        texture_data = f.read(texture_size)
                        texture.add_texture(texture_data)

                    return texture

    def __read_sprite_from_file(self, file_path: Path) -> Single:
        # if file does not exist, check for {idnex}_0.{extension} pattern
        if not file_path.exists():
            base_name = file_path.stem
            extension = file_path.suffix
            indexed_file_path = file_path.parent / f"{base_name}_0{extension}"  #
            if indexed_file_path.exists():
                file_path = indexed_file_path
                # If indexed, read all indexed files and append all to single chunk
                chunk_data = bytearray()
                index = 0
                while True:
                    indexed_file = file_path.parent / f"{base_name}_{index}{extension}"
                    if not indexed_file.exists():
                        break
                    img = Image.open(file_path)
                    # Get 8-bit pixel data
                    pixel_data = img.tobytes()
                    sprite_length = len(pixel_data) + 8
                    width, height = img.size
                    chunk_data += (
                        sprite_length.to_bytes(4)
                        + width.to_bytes(4, "little")
                        + height.to_bytes(4, "little")
                        + pixel_data
                        + (b"\0" * 4)
                    )
                    index += 1
                return Single(chunk_data)

        img = Image.open(file_path)
        # Get 8-bit pixel data
        pixel_data = img.tobytes()
        sprite_length = len(pixel_data) + 8
        width, height = img.size
        chunk_data = (
            sprite_length.to_bytes(4)
            + width.to_bytes(4, "little")
            + height.to_bytes(4, "little")
            + pixel_data
            + (b"\0" * 4)
        )
        return Single(chunk_data)

    def add(self, index: int, input_dir) -> None:
        chunk_type = CHUNK_TYPE_OVERRIDES.get(index, ChunkType.SINGLE)
        file_type = FILE_TYPE_MAP.get(index, FileType.UNKNOWN)
        file_name = FILE_NAME_MAP.get(index, f"{index:02d}")

        match file_type:
            case FileType.SPRITE:
                file_path = input_dir / EXPORT_SPRITE_FOLDER
                file_extension = EXPORT_SPRITE_EXTENSION
                self.__files.append(
                    self.__read_sprite_from_file(
                        file_path / f"{file_name}.{file_extension}"
                    )
                )
            case FileType.LOCALE:
                file_path = input_dir / EXPORT_LOCALE_FOLDER
                file_extension = EXPORT_LOCALE_EXTENSION
                blocks_count = 17
                block_data = []

                for block_id in range(blocks_count):
                    if block_id not in TEXT_BLOCKS:
                        block_path = file_path / EXPORT_LOCALE_SCRIPTS_FOLDER
                        with open(
                            block_path / f"{block_id}.{EXPORT_UNKNOWN_EXTENSION}", "rb"
                        ) as script_file:
                            script_data = script_file.read()
                            block_data.append(
                                len(script_data).to_bytes(4) + script_data
                            )
                    else:
                        file_name = TEXT_BLOCKS_NAMES.get(block_id, f"{block_id}")
                        po = polib.pofile(
                            str(file_path / f"{file_name}.{file_extension}")
                        )
                        strings_data = BytesIO()
                        for entry in po:
                            string_bytes = entry.msgstr or entry.msgid
                            strings_data.write(
                                int(entry.flags[0]).to_bytes(1)
                            )  # Unknown byte
                            string_encoded = string_bytes.encode("shift_jis")
                            strings_data.write(len(string_encoded).to_bytes(2))
                            strings_data.write(string_encoded)
                        strings_block = strings_data.getvalue()
                        block_data.append(
                            len(strings_block).to_bytes(4) + strings_block
                        )

                chunk_data = b"".join(block_data)
                self.__files.append(Single(chunk_data))
            case FileType.PALETTE:
                file_path = input_dir / EXPORT_PALETTE_FOLDER
                file_extension = EXPORT_PALETTE_EXTENSION

                # Read palette XML file
                xmlroot = ET.parse(
                    file_path / f"{file_name}.{file_extension}"
                ).getroot()
                colors = bytearray()

                for color_element in xmlroot.findall("Color"):
                    r = int(color_element.get("r", "0"))
                    g = int(color_element.get("g", "0"))
                    b = int(color_element.get("b", "0"))
                    colors.extend(bytes([b, g, r, 0]))
                palette_data = len(colors).to_bytes(4) + colors
                self.__files.append(Single(palette_data))
            case FileType.FONT:
                file_path = input_dir / EXPORT_FONT_FOLDER
                # Get characters metadata
                xmlroot = ET.parse(file_path / f"characters.xml").getroot()
                page_elements = xmlroot.findall("Page")
                page_count = len(page_elements)
                chunk = FontChunk(header_data=b"\0\0")

                for i in range(page_count):
                    page_element = page_elements[i]
                    font_page_path = file_path / f"page_{i}.png"
                    img = Image.open(font_page_path)

                    page_header = bytearray()
                    glyphs_bitmap_data = bytearray()

                    for glyph in page_element.findall("Glyph"):
                        width = int(glyph.get("width", "0"))

                        x_offset = int(glyph.get("x_offset", "0"))
                        y_offset = int(glyph.get("y_offset", "0"))

                        glyph_image = img.crop(
                            (
                                x_offset,
                                y_offset,
                                x_offset + width,
                                y_offset + FONT_GLYPH_HEIGHTS[i],
                            )
                        )

                        # Get 8-bit pixel data
                        pixel_data = glyph_image.tobytes()
                        glyph_bitmap = Font.pack_glyph_image(pixel_data)
                        page_header.extend(
                            len(glyphs_bitmap_data).to_bytes(2, "little")
                        )

                        if width != 1:
                            page_header.extend(((width - 1) << 4).to_bytes(2, "little"))
                        else:
                            page_header.extend((0).to_bytes(2))

                        if width != 1 and width != 4096:
                            glyphs_bitmap_data.extend(glyph_bitmap)

                    # page should be at minimum 20480 bytes
                    while len(page_header + glyphs_bitmap_data) < 20480:
                        glyphs_bitmap_data.extend(b"\0")

                    chunk.add_page(page_header + glyphs_bitmap_data)
                self.__files.append(chunk)
            case _:
                file_path = input_dir / EXPORT_UNKNOWN_FOLDER
                file_extension = EXPORT_UNKNOWN_EXTENSION
                self.__files.append(
                    self.__read_unknown_from_file(
                        chunk_type, file_path / f"{file_name}.{file_extension}"
                    )
                )

    def save(self, writer: BufferedWriter) -> None:
        writer.write(RESOURCE_MAGIC)
        writer.write(self.__platform.value.to_bytes(2))

        for index, file in enumerate(self.__files):
            chunk_type = CHUNK_TYPE_OVERRIDES.get(index, ChunkType.SINGLE)
            writer.write(chunk_type.value.to_bytes(2))

            match chunk_type:
                case ChunkType.SINGLE:
                    file_data = file.data.read()
                    writer.write(len(file_data).to_bytes(2))
                    writer.write(file_data)
                case _:
                    file_data = file.data.read()
                    writer.write(file_data)
