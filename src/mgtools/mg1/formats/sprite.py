from io import BytesIO
from pathlib import Path

from PIL import Image

from mgtools.file import File
from mgtools.mg1.chunks.single import Single
from mgtools.mg1.formats.palette import Palette


class Sprite(File):

    def __init__(self, chunk: Single):
        self.__image = None
        self.__parse_data(chunk.data)

    def __str__(self) -> str:
        if not self.__image:
            return "Sprite(None)"

        return f"Sprite(width={self.__image.width}, height={self.__image.height})"

    def __parse_data(self, chunk: BytesIO) -> None:
        pixel_count = int.from_bytes(chunk.read(4))
        width = int.from_bytes(chunk.read(4), "little")
        height = int.from_bytes(chunk.read(4), "little")

        pixel_data = chunk.read(pixel_count)
        self.__image = Image.frombytes("P", (width, height), pixel_data)

    def set_palette(self, palette: Palette):
        if not self.__image:
            raise ValueError("Image data is not loaded.")

        self.__image.putpalette(palette.color_map)

    def save(self, path: Path) -> None:
        if not self.__image:
            raise ValueError("Image data is not loaded.")

        self.__image.save(path)
