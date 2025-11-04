from io import BytesIO

from mgtools.chunk import Chunk


class Font(Chunk):

    @property
    def data(self) -> BytesIO:
        return BytesIO(b"".join(page for page in self.__pages))

    def __init__(self, header_data: bytes) -> None:
        self.__header = header_data
        self.__pages = []

    def add_page(self, page_data: bytes) -> None:
        self.__pages.append(page_data)
