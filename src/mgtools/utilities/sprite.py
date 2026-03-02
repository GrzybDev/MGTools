from pathlib import Path

from PIL import Image

from mgtools.resource.assets.palette import Palette


def encode_sprite_image(image: Image.Image) -> bytes:
    """Encode a PIL image into the sprite binary format (4B len + 4B w + 4B h + pixels)."""
    image_bytes = image.tobytes()

    return (
        (len(image_bytes) + 8).to_bytes(4)
        + image.width.to_bytes(4, "little")
        + image.height.to_bytes(4, "little")
        + image_bytes
    )


def encode_sprite_file(path: Path) -> bytes:
    """Open an image file and return its sprite-encoded bytes."""
    return encode_sprite_image(Image.open(path))


def decode_sprite_entry(data: bytes) -> Image.Image:
    """Decode a single sprite entry (after 4B length was already consumed)."""
    from io import BytesIO

    stream = BytesIO(data)
    width = int.from_bytes(stream.read(4), "little")
    height = int.from_bytes(stream.read(4), "little")
    pixel_data = stream.read()

    return Image.frombytes("P", (width, height), pixel_data)


def apply_palette(images: list[Image.Image], palette: "Palette | bytes") -> None:
    """Apply a Palette (or raw palette bytes) to every image in the list."""
    if isinstance(palette, bytes):
        palette_bytes = palette
    else:
        palette_bytes = palette.palette_bytes

    for image in images:
        image.putpalette(palette_bytes)


def export_images(
    images: list[Image.Image], output_path: Path, *, always_index: bool = False
) -> None:
    """Save images with optional index suffix.

    If *always_index* is True or there are multiple images, each file gets
    an ``_N`` suffix.  Otherwise the single image is saved directly.
    """
    for i, image in enumerate(images):
        if always_index or len(images) > 1:
            path = output_path.with_stem(f"{output_path.stem}_{i}")
        else:
            path = output_path

        image.save(path)
