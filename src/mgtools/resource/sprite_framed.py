import os
from io import BufferedReader, BytesIO
from pathlib import Path

from PIL import Image

from mgtools.enumerators.data_type import DataType
from mgtools.file import File
from mgtools.resource.palette import Palette


class FramedSprite(File):
    @property
    def raw_data(self) -> bytes:
        raw_bytes = self.data_type.to_bytes(2)

        data = b""

        for frame in self.__frames:
            data += self.__get_sprite_bytes(frame)

        data += (0).to_bytes(4)  # End of data marker
        raw_bytes += (len(self.__frames) * 2).to_bytes(2) + data
        return raw_bytes

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__frames: list[Image.Image] = []

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO, data_type: DataType | None = None
    ) -> "FramedSprite":
        if data_type is None:
            data_type = DataType(int.from_bytes(reader.read(2)))

        if data_type != DataType.MG1_FRAMED:
            raise ValueError("Framed sprite files must have MG1_FRAMED data type.")

        f = FramedSprite(data_type=data_type)

        frame_count = int.from_bytes(reader.read(2)) // 2

        for _ in range(frame_count):
            f.add_data(reader=reader)

        reader.seek(4, os.SEEK_CUR)
        return f

    @staticmethod
    def __get_sprite_bytes(image: Image.Image) -> bytes:
        image_bytes = image.tobytes()

        sprite_bytes = (len(image_bytes) + 8).to_bytes(4)
        sprite_bytes += image.width.to_bytes(4, "little")
        sprite_bytes += image.height.to_bytes(4, "little")
        sprite_bytes += image_bytes

        return sprite_bytes

    @staticmethod
    def __get_sprite_bytes_from_file(path: Path) -> bytes:
        image = Image.open(path)
        return FramedSprite.__get_sprite_bytes(image)

    @staticmethod
    def from_file(file_path: Path, data_type: DataType | None = None) -> "FramedSprite":
        sprite_bytes = b""

        frame_count = 0

        while True:
            current_sprite_path = file_path.with_stem(
                f"{file_path.stem}_{frame_count}"
            ).with_suffix(file_path.suffix)

            if not current_sprite_path.exists():
                break

            sprite_bytes += FramedSprite.__get_sprite_bytes_from_file(
                current_sprite_path
            )
            frame_count += 1

        sprite_bytes += (0).to_bytes(4)  # End of data marker

        return FramedSprite.from_stream(
            BytesIO(
                DataType.MG1_FRAMED.to_bytes(2)
                + (frame_count * 2).to_bytes(2)
                + sprite_bytes
            )
        )

    def add_data(self, **kwargs) -> None:
        reader = kwargs.get("reader")

        if reader is None:
            raise ValueError("Reader stream is required to add sprite data.")

        data_length = int.from_bytes(reader.read(4))

        if data_length == 0:
            raise ValueError("End of data marker reached while reading framed sprite.")

        data = BytesIO(reader.read(data_length))

        width = int.from_bytes(data.read(4), "little")
        height = int.from_bytes(data.read(4), "little")
        pixel_data = data.read()

        image = Image.frombytes("P", (width, height), pixel_data)
        self.__frames.append(image)

    def add_palette(self, palette: Palette) -> None:
        palette_bytes = palette.palette_bytes

        for frame in self.__frames:
            frame.putpalette(palette_bytes)

    def export(self, output_path: Path, **kwargs) -> None:
        for i, frame in enumerate(self.__frames):
            variant_output_path = output_path.with_stem(f"{output_path.stem}_{i}")
            frame.save(variant_output_path)
