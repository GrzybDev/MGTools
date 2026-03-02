import os
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


class FramedSprite(Asset):
    @property
    def raw_data(self) -> bytes:
        data = b"".join(encode_sprite_image(f) for f in self.__frames)
        data += (0).to_bytes(4)  # End of data marker
        return self.data_type.to_bytes(2) + (len(self.__frames) * 2).to_bytes(2) + data

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__frames: list[Image.Image] = []

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO, data_type: DataType | None = None
    ) -> Asset:
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
    def from_file(file_path: Path, data_type: DataType | None = None) -> Asset:
        sprite_bytes = b""
        frame_count = 0

        while True:
            p = file_path.with_stem(f"{file_path.stem}_{frame_count}").with_suffix(
                file_path.suffix
            )

            if not p.exists():
                break

            sprite_bytes += encode_sprite_file(p)
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

        self.__frames.append(decode_sprite_entry(reader.read(data_length)))

    def add_palette(self, palette: Palette) -> None:
        apply_palette(self.__frames, palette)

    def export(self, output_path: Path, **kwargs) -> None:
        export_images(self.__frames, output_path, always_index=True)
