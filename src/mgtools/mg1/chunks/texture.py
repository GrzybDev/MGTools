class TextureChunk:

    def __init__(self, header_data: bytes) -> None:
        self.__header = header_data
        self.__textures = []

    def add_texture(self, texture_data: bytes) -> None:
        self.__textures.append(texture_data)
