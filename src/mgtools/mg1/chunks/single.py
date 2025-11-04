from io import BytesIO

from mgtools.chunk import Chunk


class Single(Chunk):

    @property
    def data(self) -> BytesIO:
        return BytesIO(self.__data)

    def __init__(self, data: bytes):
        self.__data = data
