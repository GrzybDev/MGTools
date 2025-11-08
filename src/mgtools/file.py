from abc import ABC, abstractmethod
from io import BufferedReader, BytesIO
from pathlib import Path

from mgtools.enumerators.data_type import DataType


class File(ABC):

    @property
    def data_type(self) -> DataType:
        return self.__data_type

    @property
    @abstractmethod
    def raw_data(self) -> bytes:
        raise NotImplementedError()

    def __init__(self, data_type: DataType) -> None:
        self.__data_type: DataType = data_type

    @staticmethod
    @abstractmethod
    def from_stream(reader: BufferedReader | BytesIO) -> File:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def from_file(file_path: Path) -> File:
        raise NotImplementedError()

    @abstractmethod
    def add_data(self, **kwargs) -> None:
        raise NotImplementedError()

    @abstractmethod
    def export(self, output_path: Path, **kwargs) -> None:
        raise NotImplementedError()
