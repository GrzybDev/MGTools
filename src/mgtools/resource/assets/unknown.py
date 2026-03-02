import os
from io import BufferedReader, BytesIO
from pathlib import Path

from mgtools.enumerators.data_type import DataType
from mgtools.resource.asset import Asset


class UnknownFile(Asset):
    @property
    def raw_data(self) -> bytes:
        if self.data_type == DataType.MG2_SECTION:
            raw_bytes = b""
            for entry in self.__data:
                raw_bytes += len(entry).to_bytes(4, "big") + entry
            return raw_bytes

        raw_bytes = self.data_type.to_bytes(2)

        match self.data_type:
            case DataType.MG1_SECTION:
                raw_bytes += len(self.__data[0]).to_bytes(2) + self.__data[0]
            case DataType.MG1_FRAMED:
                raw_bytes += (len(self.__data) * 2).to_bytes(2)

                for entry in self.__data:
                    raw_bytes += len(entry).to_bytes(4) + entry

                raw_bytes += (0).to_bytes(4)  # Padding
            case DataType.MG1_FONT | DataType.MG1_TEXTURE:
                raw_bytes += b"\0\0"  # Identifier placeholder

                for entry in self.__data:
                    raw_bytes += len(entry).to_bytes(4) + entry

        return raw_bytes

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__data: list[bytes] = []

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO, data_type: DataType | None = None
    ) -> Asset:
        if data_type is None:
            data_type = DataType(int.from_bytes(reader.read(2)))

        f = UnknownFile(data_type)

        match data_type:
            case DataType.MG1_SECTION:
                data_length = int.from_bytes(reader.read(2))
                data = reader.read(data_length)

                f.add_data(file_data=data)
            case DataType.MG1_FRAMED:
                entries_count = int.from_bytes(reader.read(2)) // 2

                for _ in range(entries_count):
                    entry_length = int.from_bytes(reader.read(4))
                    data = reader.read(entry_length)
                    f.add_data(file_data=data)

                reader.seek(4, os.SEEK_CUR)  # Skip padding
            case DataType.MG1_FONT:
                identifier = reader.read(  # noqa: F841
                    2
                )  # Figure out the meaning of this

                for _ in range(5):  # Figure out where this 5 comes from
                    entry_size = int.from_bytes(reader.read(4))
                    entry_data = reader.read(entry_size)
                    f.add_data(file_data=entry_data)
            case DataType.MG1_TEXTURE:
                identifier = reader.read(  # noqa: F841
                    2
                )  # Figure out the meaning of this

                for _ in range(2):  # Figure out where this 2 comes from
                    entry_size = int.from_bytes(reader.read(4))
                    entry_data = reader.read(entry_size)
                    f.add_data(file_data=entry_data)
            case DataType.MG2_SECTION:
                while size_bytes := reader.read(4):
                    block_size = int.from_bytes(size_bytes, "big")
                    block_data = reader.read(block_size)
                    f.add_data(file_data=block_data)

        return f

    @staticmethod
    def from_file(file_path: Path, data_type: DataType | None = None) -> Asset:
        if data_type is None:
            raise ValueError("Data type must be provided for UnknownFile.")

        with open(file_path, "rb") as f:
            data = f.read()

            if data_type == DataType.MG2_SECTION:
                return UnknownFile.from_stream(BytesIO(data), data_type=data_type)

            return UnknownFile.from_stream(BytesIO(data))

    def add_data(self, **kwargs) -> None:
        if "file_data" not in kwargs:
            raise ValueError("Missing 'file_data' argument.")

        self.__data.append(kwargs["file_data"])

    def export(self, output_path: Path, **kwargs) -> None:
        with open(output_path, "wb") as f:
            f.write(self.raw_data)
