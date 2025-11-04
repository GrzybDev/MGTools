from io import BytesIO


class SingleChunk:

    @property
    def data(self) -> BytesIO:
        return BytesIO(self.__data)

    def __init__(self, data: bytes):
        self.__data = data
