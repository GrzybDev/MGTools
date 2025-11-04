import os
from io import BufferedReader

import typer

from mgtools.mg1.chunks.animated_sprite import AnimatedSpriteChunk
from mgtools.mg1.chunks.font import FontChunk
from mgtools.mg1.chunks.single import SingleChunk
from mgtools.mg1.chunks.texture import TextureChunk
from mgtools.mg1.constants import RESOURCE_MAGIC
from mgtools.mg1.enumerators.chunk_type import ChunkType
from mgtools.mg1.enumerators.resource_platform import ResourcePlatform


class Resource:

    def __init__(self) -> None:
        self.__platform = ResourcePlatform.UNKNOWN
        self.__files = []

    def __str__(self) -> str:
        return f"Resource(platform={self.__platform.name}, files_count={len(self.__files)})"

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

    def __read_chunk(self, reader: BufferedReader) -> SingleChunk:
        file_size = int.from_bytes(reader.read(2))
        file_data = reader.read(file_size)

        return SingleChunk(file_data)

    def __read_animated_sprite_chunk(
        self, reader: BufferedReader
    ) -> AnimatedSpriteChunk:
        anim = AnimatedSpriteChunk()
        frame_count = int.from_bytes(reader.read(2)) // 2

        for _ in range(frame_count):
            frame_file_size = int.from_bytes(reader.read(4))
            frame_data = reader.read(frame_file_size)
            anim.add_frame(SingleChunk(frame_data))

        reader.seek(4, os.SEEK_CUR)  # Skip padding/alignment bytes
        return anim

    def __read_font_chunk(self, reader: BufferedReader) -> FontChunk:
        font = FontChunk(reader.read(2))

        for _ in range(5):  # Figure out where this 5 comes from
            page_size = int.from_bytes(reader.read(4))
            page_data = reader.read(page_size)
            font.add_page(page_data)

        return font

    def __read_texture_chunk(self, reader: BufferedReader) -> TextureChunk:
        header_data = reader.read(2)
        texture = TextureChunk(header_data)

        for _ in range(2):  # Figure out where this 2 comes from
            texture_size = int.from_bytes(reader.read(4))
            texture_data = reader.read(texture_size)
            texture.add_texture(texture_data)

        return texture
