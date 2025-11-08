from io import BufferedReader, BytesIO
from pathlib import Path

from PIL import Image

from mgtools.enumerators.data_type import DataType
from mgtools.file import File
from mgtools.readers.palette import Palette


class Sprite(File):

    @property
    def raw_data(self) -> bytes:
        raw_bytes = self.data_type.to_bytes(2)

        data = b""

        for variant in self.__variants:
            data += self.__get_sprite_bytes(variant)

        data += (0).to_bytes(4)  # End of data marker
        raw_bytes += len(data).to_bytes(2) + data
        return raw_bytes

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__variants: list[Image.Image] = []

    @staticmethod
    def from_stream(reader: BufferedReader | BytesIO) -> Sprite:
        data_type = DataType(int.from_bytes(reader.read(2)))

        if data_type != DataType.SIMPLE:
            raise ValueError("Sprite files must have SIMPLE data type.")

        f = Sprite(data_type=data_type)

        data_length = int.from_bytes(reader.read(2))
        data = reader.read(data_length)

        f.add_data(reader=BytesIO(data))

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
        return Sprite.__get_sprite_bytes(image)

    @staticmethod
    def from_file(file_path: Path) -> Sprite:
        sprite_bytes = b""

        if not file_path.exists():
            # Check if any variant file exists
            base_name = file_path.stem
            extension = file_path.suffix
            indexed_file_path = file_path.parent / f"{base_name}_0{extension}"

            if not indexed_file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            current_index = 0

            while True:
                indexed_file_path = (
                    file_path.parent / f"{base_name}_{current_index}{extension}"
                )
                if not indexed_file_path.exists():
                    break

                current_index += 1
                sprite_bytes += Sprite.__get_sprite_bytes_from_file(indexed_file_path)
        else:
            sprite_bytes += Sprite.__get_sprite_bytes_from_file(file_path)

        sprite_bytes += (0).to_bytes(4)  # End of data marker

        return Sprite.from_stream(
            BytesIO(
                DataType.SIMPLE.to_bytes(2)
                + len(sprite_bytes).to_bytes(2)
                + sprite_bytes
            )
        )

    def add_data(self, **kwargs) -> None:
        reader = kwargs.get("reader")

        if reader is None:
            raise ValueError("Reader stream is required to add sprite data.")

        while True:
            data_length = int.from_bytes(reader.read(4))

            if data_length == 0:
                break

            data = BytesIO(reader.read(data_length))

            width = int.from_bytes(data.read(4), "little")
            height = int.from_bytes(data.read(4), "little")
            pixel_data = data.read()

            image = Image.frombytes("P", (width, height), pixel_data)
            self.__variants.append(image)

    def add_palette(self, palette: Palette) -> None:
        palette_bytes = palette.palette_bytes

        for i in range(len(self.__variants)):
            self.__variants[i].putpalette(palette_bytes)

    def export(self, output_path: Path, **kwargs) -> None:
        for i, variant in enumerate(self.__variants):
            if len(self.__variants) > 1:
                variant_output_path = output_path.with_stem(f"{output_path.stem}_{i}")
            else:
                variant_output_path = output_path

            variant.save(variant_output_path)
