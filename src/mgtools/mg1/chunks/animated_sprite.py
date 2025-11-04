from io import BytesIO

from mgtools.chunk import Chunk
from mgtools.mg1.chunks.single import Single


class AnimatedSprite(Chunk):

    @property
    def data(self) -> BytesIO:
        return BytesIO(b"".join(frame.data.read() for frame in self.__frames))

    def __init__(self):
        self.__frames = []

    def add_frame(self, frame: Single) -> None:
        self.__frames.append(frame)
