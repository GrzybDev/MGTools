import struct
from dataclasses import dataclass

from PIL import Image


@dataclass
class MgsGlyph:
    char_code: int
    width: int
    height: int
    bearing_x: int
    bearing_y: int
    advance: int
    pixel_data: bytes = b""

    def to_image(self) -> Image.Image | None:
        # Convert glyph pixel data to a PIL Image (grayscale).
        if self.width == 0 or self.height == 0:
            return None
        return Image.frombytes("L", (self.width, self.height), self.pixel_data)

    def data_bytes(self) -> bytes:
        # Serialize glyph data (5-byte header + pixel data).
        return (
            struct.pack(
                "BBBBB",
                self.width,
                self.height,
                self.bearing_x,
                self.bearing_y,
                self.advance,
            )
            + self.pixel_data
        )
