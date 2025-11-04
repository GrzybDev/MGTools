from io import BytesIO

from PIL import Image

from mgtools.mg1.chunks.single import SingleChunk
from mgtools.mg1.formats.palette import Palette


class Sprite:

    __header_bytes = b""

    def __init__(self, chunk: SingleChunk):
        self.__parse_data(chunk.data)

    def __parse_data(self, chunk: BytesIO) -> None:
        self.__header_bytes = chunk.read(4)

        width = int.from_bytes(chunk.read(4), "little")
        height = int.from_bytes(chunk.read(4), "little")

        pixel_data = chunk.read(width * height)
        self.__image = Image.frombytes("P", (width, height), pixel_data)

    def set_palette(self, palette: Palette):
        self.__image.putpalette(palette.color_map)

    def save(self, path: str) -> None:
        self.__image.save(path)
