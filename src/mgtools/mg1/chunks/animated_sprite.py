from mgtools.mg1.chunks.single import SingleChunk


class AnimatedSpriteChunk:

    def __init__(self):
        self.__frames = []

    def add_frame(self, frame: SingleChunk) -> None:
        self.__frames.append(frame)
