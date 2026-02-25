import json
from io import BytesIO
from pathlib import Path

import typer
from PIL import Image

from mgtools.constants import TXTR_ALIGNMENT, TXTR_HEADER_SIZE, TXTR_MAGIC
from mgtools.dataclasses.ctxr_header import CtxrHeader
from mgtools.dataclasses.ctxr_miplevel import CtxrMipLevel


class Ctxr:
    def __init__(
        self,
        header: CtxrHeader,
        texture_data: bytes,
        mipmaps: list[CtxrMipLevel] | None = None,
    ) -> None:
        self.header = header
        self.texture_data = texture_data
        self.mipmaps = mipmaps if mipmaps is not None else []

    @staticmethod
    def _is_power_of_2(n: int) -> bool:
        return n > 0 and (n & (n - 1)) == 0

    @staticmethod
    def _align(offset: int, alignment: int = TXTR_ALIGNMENT) -> int:
        return ((offset + alignment - 1) // alignment) * alignment

    @classmethod
    def from_file(cls, path: Path) -> "Ctxr":
        # Parse a CTXR file, extracting header, texture data, and mipmaps.
        data = path.read_bytes()
        return cls.from_bytes(data)

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ctxr":
        # Parse CTXR from raw bytes.
        if len(data) < TXTR_HEADER_SIZE:
            raise ValueError("File too small to be a valid CTXR.")

        if data[0:4] != TXTR_MAGIC:
            raise ValueError(
                f"Not a valid CTXR file (expected magic {TXTR_MAGIC!r}, got {data[0:4]!r})."
            )

        header = CtxrHeader(
            padding=int.from_bytes(data[0x04:0x06]),
            version=int.from_bytes(data[0x06:0x08]),
            width=int.from_bytes(data[0x08:0x0A]),
            height=int.from_bytes(data[0x0A:0x0C]),
            unknown_0c=int.from_bytes(data[0x0C:0x0E]),
            unknown_0e=int.from_bytes(data[0x0E:0x10]),
            unknown_10=int.from_bytes(data[0x10:0x14]),
            color_0=bytes(data[0x14:0x18]),
            color_1=bytes(data[0x18:0x1C]),
            color_2=bytes(data[0x1C:0x20]),
            color_3=bytes(data[0x20:0x24]),
            unknown_24=int.from_bytes(data[0x24:0x28]),
            reserved=bytes(data[0x28:0x80]),
        )

        texture_data_size = int.from_bytes(data[0x80:0x84])
        expected_size = header.width * header.height * 4

        if texture_data_size != expected_size:
            raise ValueError(
                f"Texture data size mismatch: header says {texture_data_size}, "
                f"expected {expected_size} ({header.width}x{header.height}x4)."
            )

        texture_data = bytes(data[0x84 : 0x84 + texture_data_size])

        # Parse mipmaps if dimensions are power-of-2
        mipmaps: list[CtxrMipLevel] = []
        if cls._is_power_of_2(header.width) and cls._is_power_of_2(header.height):
            pos = 0x84 + texture_data_size
            mw, mh = header.width, header.height

            while mw > 1 or mh > 1:
                mw = max(mw // 2, 1)
                mh = max(mh // 2, 1)

                pos = cls._align(pos)
                if pos + 4 > len(data):
                    break

                mip_size = int.from_bytes(data[pos : pos + 4])
                pos += 4

                expected_mip = mw * mh * 4
                if mip_size != expected_mip:
                    break

                if pos + mip_size > len(data):
                    break

                mip_data = bytes(data[pos : pos + mip_size])
                mipmaps.append(CtxrMipLevel(width=mw, height=mh, data=mip_data))
                pos += mip_size

        return cls(header=header, texture_data=texture_data, mipmaps=mipmaps)

    def to_bytes(self) -> bytes:
        # Serialize back to CTXR binary format.
        buf = BytesIO()

        # Magic
        buf.write(TXTR_MAGIC)
        # Header fields (big-endian)
        buf.write(self.header.padding.to_bytes(2))
        buf.write(self.header.version.to_bytes(2))
        buf.write(self.header.width.to_bytes(2))
        buf.write(self.header.height.to_bytes(2))
        buf.write(self.header.unknown_0c.to_bytes(2))
        buf.write(self.header.unknown_0e.to_bytes(2))
        buf.write(self.header.unknown_10.to_bytes(4))
        buf.write(self.header.color_0)
        buf.write(self.header.color_1)
        buf.write(self.header.color_2)
        buf.write(self.header.color_3)
        buf.write(self.header.unknown_24.to_bytes(4))
        buf.write(self.header.reserved)

        # Texture data size + data
        data_size = self.header.width * self.header.height * 4
        buf.write(data_size.to_bytes(4))
        buf.write(self.texture_data)

        # Mipmaps
        for mip in self.mipmaps:
            # Pad to alignment
            pos = buf.tell()
            aligned = self._align(pos)
            buf.write(b"\x00" * (aligned - pos))

            mip_size = mip.width * mip.height * 4
            buf.write(mip_size.to_bytes(4))
            buf.write(mip.data)

        # Final alignment padding
        pos = buf.tell()
        aligned = self._align(pos)
        buf.write(b"\x00" * (aligned - pos))

        return buf.getvalue()

    def to_file(self, path: Path) -> None:
        # Write CTXR to file.
        path.write_bytes(self.to_bytes())

    def to_image(self) -> Image.Image:
        # Convert main texture data to a PIL Image.
        return Image.frombytes(
            "RGBA", (self.header.width, self.header.height), self.texture_data
        )

    def save_metadata(self, path: Path) -> None:
        # Save header metadata as JSON (for round-trip reconstruction).
        meta = {
            "padding": self.header.padding,
            "version": self.header.version,
            "width": self.header.width,
            "height": self.header.height,
            "unknown_0c": self.header.unknown_0c,
            "unknown_0e": self.header.unknown_0e,
            "unknown_10": self.header.unknown_10,
            "color_0": self.header.color_0.hex(),
            "color_1": self.header.color_1.hex(),
            "color_2": self.header.color_2.hex(),
            "color_3": self.header.color_3.hex(),
            "unknown_24": self.header.unknown_24,
            "reserved": self.header.reserved.hex(),
            "mipmap_count": len(self.mipmaps),
        }
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def from_image(cls, image: Image.Image, metadata_path: Path) -> "Ctxr":
        # Create a CTXR from a PNG image and a previously saved metadata JSON.
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))

        image = image.convert("RGBA")
        texture_data = image.tobytes()

        header = CtxrHeader(
            padding=meta["padding"],
            version=meta["version"],
            width=image.width,
            height=image.height,
            unknown_0c=meta["unknown_0c"],
            unknown_0e=meta["unknown_0e"],
            unknown_10=meta["unknown_10"],
            color_0=bytes.fromhex(meta["color_0"]),
            color_1=bytes.fromhex(meta["color_1"]),
            color_2=bytes.fromhex(meta["color_2"]),
            color_3=bytes.fromhex(meta["color_3"]),
            unknown_24=meta["unknown_24"],
            reserved=bytes.fromhex(meta["reserved"]),
        )

        # Regenerate mipmaps if the original had them
        mipmaps: list[CtxrMipLevel] = []
        mipmap_count = meta.get("mipmap_count", 0)
        if mipmap_count > 0:
            mw, mh = image.width, image.height
            mip_img = image.copy()
            for _ in range(mipmap_count):
                mw = max(mw // 2, 1)
                mh = max(mh // 2, 1)
                mip_img = mip_img.resize((mw, mh), Image.Resampling.LANCZOS)
                mipmaps.append(
                    CtxrMipLevel(width=mw, height=mh, data=mip_img.tobytes())
                )

        return cls(header=header, texture_data=texture_data, mipmaps=mipmaps)


def export_ctxr(input_file: Path, output_file: Path):
    typer.echo(f"Exporting {input_file} to {output_file}...")

    ctxr = Ctxr.from_file(input_file)

    typer.echo(f"CTXR version: {ctxr.header.version}")
    typer.echo(f"Texture dimensions: {ctxr.header.width}x{ctxr.header.height}")
    typer.echo(f"Mipmap levels: {len(ctxr.mipmaps)}")

    # Save the image
    image = ctxr.to_image()
    image.save(output_file)

    # Save metadata alongside the image for round-trip support
    meta_file = output_file.with_suffix(".ctxr.json")
    ctxr.save_metadata(meta_file)
    typer.echo(f"Metadata saved to {meta_file}")


def import_ctxr(png_file: Path, output_dir: Path):
    meta_file = png_file.with_suffix(".ctxr.json")

    if not meta_file.exists():
        typer.echo(
            f"Skipping {png_file.name}: metadata file {meta_file.name} not found."
        )
        return

    typer.echo(f"Importing {png_file} ...")
    image = Image.open(png_file)
    ctxr = Ctxr.from_image(image, meta_file)
    output_file = output_dir / f"{png_file.stem}.ctxr"
    ctxr.to_file(output_file)
    typer.echo(f"Written to {output_file}")
