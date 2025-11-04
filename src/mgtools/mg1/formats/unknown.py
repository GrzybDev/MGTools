from pathlib import Path

from mgtools.file import File
from mgtools.mg1.chunks.single import Single


class Unknown(File):

    __raw_data = b""

    def __init__(self, chunk: Single):
        self.__raw_data = chunk.data.read()

    def save(self, path: Path) -> None:
        with path.open("wb") as f:
            f.write(self.__raw_data)
