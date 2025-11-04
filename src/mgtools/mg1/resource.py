import os
from io import BufferedReader

from mgtools.mg1.chunks.animated_sprite import AnimatedSprite
from mgtools.mg1.chunks.font import Font
from mgtools.mg1.chunks.single import Single
from mgtools.mg1.chunks.texture import Texture
from mgtools.mg1.constants import RESOURCE_MAGIC
from mgtools.mg1.enumerators.chunk_type import ChunkType
from mgtools.mg1.enumerators.file_type import FileType
from mgtools.mg1.enumerators.resource_platform import ResourcePlatform
from mgtools.mg1.formats.palette import Palette
from mgtools.mg1.formats.sprite import Sprite
from mgtools.mg1.mappings import FILE_TYPE_MAP


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

    def __read_font_chunk(self, reader: BufferedReader) -> Font:
        font = Font(reader.read(2))

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
