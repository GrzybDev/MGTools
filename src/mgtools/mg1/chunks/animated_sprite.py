from io import BytesIO

from mgtools.chunk import Chunk
from mgtools.mg1.chunks.single import Single


class AnimatedSprite(Chunk):

    @property
    def data(self) -> BytesIO:
        init_bytes = (len(self.__frames) * 2).to_bytes(2)
        frame_data = [frame.data.read() for frame in self.__frames]
        full_frame_bytes = [len(frame).to_bytes(4) + frame for frame in frame_data]
        return BytesIO(init_bytes + b"".join(full_frame_bytes) + (b"\0" * 4))

    def __init__(self):
        self.__frames = []

    def add_frame(self, frame: Single) -> None:
        self.__frames.append(frame)
