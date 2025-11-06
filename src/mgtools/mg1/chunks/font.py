from io import BytesIO

from mgtools.chunk import Chunk


class Font(Chunk):

    @property
    def data(self) -> BytesIO:
        page_bytes = [len(page).to_bytes(4) + page for page in self.__pages]
        return BytesIO(self.__header_bytes + b"".join(page_bytes))

    @property
    def page_count(self) -> int:
        return len(self.__pages)

    def __init__(self, header_data: bytes) -> None:
        self.__header_bytes = header_data
        self.__pages = []

    def add_page(self, page_data: bytes) -> None:
        self.__pages.append(page_data)

    def get_page(self, index: int) -> BytesIO:
        return BytesIO(self.__pages[index])
