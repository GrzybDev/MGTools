from io import BytesIO

from mgtools.chunk import Chunk


class Texture(Chunk):

    @property
    def data(self) -> BytesIO:
        return BytesIO(self.__header_bytes + b"".join(tex for tex in self.__textures))

    def __init__(self, header_data: bytes) -> None:
        self.__header_bytes = header_data
        self.__textures = []

    def add_texture(self, texture_data: bytes) -> None:
        self.__textures.append(texture_data)
