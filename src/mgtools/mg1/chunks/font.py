class FontChunk:

    def __init__(self, header_data: bytes) -> None:
        self.__header = header_data
        self.__pages = []

    def add_page(self, page_data: bytes) -> None:
        self.__pages.append(page_data)
