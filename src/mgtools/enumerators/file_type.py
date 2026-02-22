from enum import Enum


class FileType(Enum):
    UNKNOWN = -1
    PALETTE = 0
    SPRITE = 1
    LOCALE = 2
    FONT = 3
    SPRITE_FRAMED = 4
    TEXTURE = 5
