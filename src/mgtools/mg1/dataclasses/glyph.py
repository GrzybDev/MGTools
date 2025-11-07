from dataclasses import dataclass

from PIL import Image


@dataclass
class Glyph:
    char: str
    offset: int
    width: int
    image: Image.Image | None = None
    x_offset: int = 0
    y_offset: int = 0
