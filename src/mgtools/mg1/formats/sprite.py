from io import BytesIO
from pathlib import Path

from PIL import Image

from mgtools.file import File
from mgtools.mg1.chunks.single import Single
from mgtools.mg1.formats.palette import Palette


class Sprite(File):

    def __init__(self, chunk: Single):
        self.__images = []
        self.__parse_data(chunk.data)

    def __str__(self) -> str:
        if not self.__images:
            return "Sprite(None)"

        return f"Sprite()"

    def __parse_data(self, chunk: BytesIO) -> None:
        while True:
            sprite_length = int.from_bytes(chunk.read(4))

            if sprite_length == 0:
                break

            sprite_data = BytesIO(chunk.read(sprite_length))

            width = int.from_bytes(sprite_data.read(4), "little")
            height = int.from_bytes(sprite_data.read(4), "little")

            pixel_data = sprite_data.read()
            image = Image.frombytes("P", (width, height), pixel_data)
            self.__images.append(image)

    def set_palette(self, palette: Palette):
        if not self.__images:
            raise ValueError("Image data is not loaded.")

        for image in self.__images:
            image.putpalette(palette.color_map)

    def save(self, path: Path) -> None:
        if not self.__images:
            raise ValueError("Image data is not loaded.")

        for i, self.__image in enumerate(self.__images):
            if len(self.__images) > 1:
                self.__image.save(path.with_name(f"{path.stem}_{i}{path.suffix}"))
            else:
                self.__image.save(path)
