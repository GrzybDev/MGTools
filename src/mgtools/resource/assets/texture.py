from io import BufferedReader, BytesIO
from pathlib import Path

from PIL import Image

from mgtools.enumerators.data_type import DataType
from mgtools.resource.asset import Asset


class Texture(Asset):
    @property
    def raw_data(self) -> bytes:
        if self.data_type == DataType.MG2_SECTION:
            raw_bytes = b""
            for layer in self.__layers:
                raw_bytes += self.__get_texture_bytes(layer)
            return raw_bytes

        raw_bytes = self.data_type.to_bytes(2)
        raw_bytes += self.__identifier

        for layer in self.__layers:
            raw_bytes += self.__get_texture_bytes(layer)

        return raw_bytes

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__layers: list[Image.Image] = []
        self.__identifier = b"\0\0"

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO, data_type: DataType | None = None
    ) -> Asset:
        if data_type is None:
            data_type = DataType(int.from_bytes(reader.read(2)))

        if data_type == DataType.MG2_SECTION:
            f = Texture(data_type=data_type)
            f.add_data(reader=reader)
            f.add_data(reader=reader)
            return f

        if data_type != DataType.MG1_TEXTURE:
            raise ValueError("Texture files must have MG1_TEXTURE data type.")

        f = Texture(data_type=data_type)
        f.__identifier = reader.read(2)
        f.add_data(reader=reader)
        f.add_data(reader=reader)

        return f

    @staticmethod
    def __get_texture_bytes(image: Image.Image) -> bytes:
        image_bytes = image.tobytes()

        texture_bytes = (len(image_bytes) + 2).to_bytes(4)
        texture_bytes += image_bytes
        texture_bytes += (0).to_bytes(2)  # End of layer marker

        return texture_bytes

    @staticmethod
    def __get_texture_bytes_from_file(path: Path) -> bytes:
        image = Image.open(path)
        return Texture.__get_texture_bytes(image)

    @staticmethod
    def from_file(
        file_path: Path, data_type: DataType | None = None, **kwargs
    ) -> Asset:
        identifier = kwargs.get("identifier", b"\0\0")
        texture_bytes = b""

        layers_count = 0

        while True:
            current_texture_path = file_path.with_stem(
                f"{file_path.stem}_{layers_count}"
            ).with_suffix(file_path.suffix)

            if not current_texture_path.exists():
                break

            texture_bytes += Texture.__get_texture_bytes_from_file(current_texture_path)
            layers_count += 1

        texture_bytes += (0).to_bytes(2)  # End of layer marker

        if data_type == DataType.MG2_SECTION:
            return Texture.from_stream(
                BytesIO(texture_bytes), data_type=DataType.MG2_SECTION
            )

        return Texture.from_stream(
            BytesIO(DataType.MG1_TEXTURE.to_bytes(2) + identifier + texture_bytes)
        )

    def add_data(self, **kwargs) -> None:
        reader = kwargs.get("reader")
        if reader is None:
            raise ValueError("add_data requires a 'reader' keyword argument.")

        data_length = int.from_bytes(reader.read(4))

        width = 512
        height = 424

        calculated_data_length = (
            (width * height) * 3
        ) + 2  # Image data length + end of layer marker

        if data_length != calculated_data_length:
            raise ValueError(
                f"Expected data length of {calculated_data_length} bytes, but got {data_length} bytes."
            )

        image_bytes = reader.read(data_length)
        image = Image.frombytes("RGB", (width, height), image_bytes)
        self.__layers.append(image)

    def export(self, output_path: Path, **kwargs) -> None:
        for i, layer in enumerate(self.__layers):
            variant_output_path = output_path.with_stem(f"{output_path.stem}_{i}")
            layer.save(variant_output_path)
