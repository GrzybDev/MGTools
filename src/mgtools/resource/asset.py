from abc import ABC, abstractmethod
from io import BufferedReader, BytesIO
from pathlib import Path

from mgtools.enumerators.data_type import DataType


class Asset(ABC):
    @property
    def data_type(self) -> DataType:
        return self.__data_type

    @property
    @abstractmethod
    def raw_data(self) -> bytes: ...

    def __init__(self, data_type: DataType) -> None:
        self.__data_type: DataType = data_type

    @staticmethod
    @abstractmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
        data_type: DataType | None = None,
    ) -> "Asset": ...

    @staticmethod
    @abstractmethod
    def from_file(
        file_path: Path,
        data_type: DataType | None = None,
    ) -> "Asset": ...

    @abstractmethod
    def add_data(self, **kwargs) -> None: ...

    @abstractmethod
    def export(self, output_path: Path, **kwargs) -> None: ...
