from io import BufferedReader, BytesIO
from pathlib import Path

from PIL import Image

from mgtools.enumerators.data_type import DataType
from mgtools.resource.asset import Asset
from mgtools.resource.assets.palette import Palette
from mgtools.utilities.sprite import (
    apply_palette,
    decode_sprite_entry,
    encode_sprite_file,
    encode_sprite_image,
    export_images,
)


class Sprite(Asset):
    @property
    def raw_data(self) -> bytes:
        data = b"".join(encode_sprite_image(v) for v in self.__variants)
        data += (0).to_bytes(4)  # End of data marker
        return self.data_type.to_bytes(2) + len(data).to_bytes(2) + data

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__variants: list[Image.Image] = []

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO, data_type: DataType | None = None
    ) -> Asset:
        if data_type is None:
            data_type = DataType(int.from_bytes(reader.read(2)))

        if data_type != DataType.MG1_SECTION:
            raise ValueError("Sprite files must have MG1_SECTION data type.")

        f = Sprite(data_type=data_type)

        data_length = int.from_bytes(reader.read(2))
        data = reader.read(data_length)

        f.add_data(reader=BytesIO(data))

        return f

    @staticmethod
    def from_file(file_path: Path, data_type: DataType | None = None) -> Asset:
        sprite_bytes = b""

        if not file_path.exists():
            base_name = file_path.stem
            extension = file_path.suffix
            first = file_path.parent / f"{base_name}_0{extension}"

            if not first.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            idx = 0
            while True:
                p = file_path.parent / f"{base_name}_{idx}{extension}"
                if not p.exists():
                    break
                sprite_bytes += encode_sprite_file(p)
                idx += 1
        else:
            sprite_bytes += encode_sprite_file(file_path)

        sprite_bytes += (0).to_bytes(4)  # End of data marker

        return Sprite.from_stream(
            BytesIO(
                DataType.MG1_SECTION.to_bytes(2)
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

            self.__variants.append(decode_sprite_entry(reader.read(data_length)))

    def add_palette(self, palette: Palette) -> None:
        apply_palette(self.__variants, palette)

    def export(self, output_path: Path, **kwargs) -> None:
        export_images(self.__variants, output_path)
