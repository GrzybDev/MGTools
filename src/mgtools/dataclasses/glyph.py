from dataclasses import dataclass

from PIL import Image


@dataclass
class Glyph:
    index: int
    char: str
    offset: int
    width: int
    image: Image.Image | None = None
    x_offset: int = 0
    y_offset: int = 0
    packed_size: int = 0
    tail_data: bytes = b""
    pad_bits: int = 0
