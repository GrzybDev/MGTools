import json
import struct
from io import BytesIO
from pathlib import Path

import typer
from PIL import Image

from mgtools.constants import FONT_GLYPH_HEADER_SIZE, FONT_HEADER_SIZE, FONT_MAGIC
from mgtools.dataclasses.mgs_glyph import MgsGlyph


class MgsFont:
    def __init__(
        self,
        max_width: int,
        max_height: int,
        unknown_0c: int,
        glyphs: list[MgsGlyph],
        duplicate_indices: list[tuple[int, int]] | None = None,
    ) -> None:
        self.max_width = max_width
        self.max_height = max_height
        self.unknown_0c = unknown_0c
        self.glyphs = glyphs
        # duplicate_indices: list of (table_index, source_glyph_list_index)
        # for entries that point to the same data as another entry
        self.duplicate_indices = duplicate_indices or []

    @classmethod
    def from_file(cls, path: Path) -> "MgsFont":
        # Parse a MGS font file.
        data = path.read_bytes()
        return cls.from_bytes(data)

    @classmethod
    def from_bytes(cls, data: bytes) -> "MgsFont":
        # Parse MGS font from raw bytes.
        if len(data) < FONT_HEADER_SIZE:
            raise ValueError("File too small to be a valid MGS font.")

        if data[0:4] != FONT_MAGIC:
            raise ValueError(
                f"Not a valid MGS font file (expected magic {FONT_MAGIC!r}, "
                f"got {data[0:4]!r})."
            )

        max_width, max_height, unknown_0c, table_offset, glyph_count = (
            struct.unpack_from("<IIIII", data, 0x04)
        )

        # Parse glyph table
        table_entries: list[tuple[int, int]] = []
        for i in range(glyph_count):
            off = table_offset + i * 8
            char_code, data_off = struct.unpack_from("<II", data, off)
            table_entries.append((char_code, data_off))

        # Build glyphs, tracking duplicates (entries sharing the same offset)
        glyphs: list[MgsGlyph] = []
        duplicate_indices: list[tuple[int, int]] = []
        offset_to_glyph_idx: dict[int, int] = {}

        for i, (char_code, data_off) in enumerate(table_entries):
            if data_off in offset_to_glyph_idx:
                # Duplicate entry — points to same data as a previous glyph
                duplicate_indices.append((i, offset_to_glyph_idx[data_off]))
                continue

            if data_off + FONT_GLYPH_HEADER_SIZE > len(data):
                raise ValueError(
                    f"Glyph {i} (U+{char_code:04X}) data offset 0x{data_off:X} "
                    f"exceeds file size."
                )

            w, h, bx, by, adv = struct.unpack_from("BBBBB", data, data_off)
            pixel_size = w * h
            pixel_start = data_off + FONT_GLYPH_HEADER_SIZE
            pixel_end = pixel_start + pixel_size

            if pixel_end > len(data):
                raise ValueError(
                    f"Glyph {i} (U+{char_code:04X}) pixel data extends beyond "
                    f"file (need {pixel_size} bytes at 0x{pixel_start:X})."
                )

            pixel_data = bytes(data[pixel_start:pixel_end])

            offset_to_glyph_idx[data_off] = len(glyphs)
            glyphs.append(
                MgsGlyph(
                    char_code=char_code,
                    width=w,
                    height=h,
                    bearing_x=bx,
                    bearing_y=by,
                    advance=adv,
                    pixel_data=pixel_data,
                )
            )

        return cls(
            max_width=max_width,
            max_height=max_height,
            unknown_0c=unknown_0c,
            glyphs=glyphs,
            duplicate_indices=duplicate_indices,
        )

    def to_bytes(self) -> bytes:
        # Serialize back to MGS font binary format.
        buf = BytesIO()

        # Build the full table entry list (glyphs + duplicates merged in order)
        # First, build a mapping: glyph_list_index -> table_index
        # and duplicate table entries
        total_entries = len(self.glyphs) + len(self.duplicate_indices)

        # Build ordered list of (table_index, glyph_or_dup)
        glyph_table_indices: list[int] = []
        dup_set = {d[0] for d in self.duplicate_indices}
        dup_map = {d[0]: d[1] for d in self.duplicate_indices}

        glyph_idx = 0
        for table_idx in range(total_entries):
            if table_idx in dup_set:
                glyph_table_indices.append(-1)  # placeholder for duplicate
            else:
                glyph_table_indices.append(glyph_idx)
                glyph_idx += 1

        table_offset = FONT_HEADER_SIZE
        data_start = table_offset + total_entries * 8

        # Serialize glyph data and compute offsets
        glyph_data_blobs: list[bytes] = []
        glyph_offsets: list[int] = []
        current_offset = data_start

        for glyph in self.glyphs:
            glyph_offsets.append(current_offset)
            blob = glyph.data_bytes()
            glyph_data_blobs.append(blob)
            current_offset += len(blob)

        # Write header
        buf.write(FONT_MAGIC)
        buf.write(
            struct.pack(
                "<IIIII",
                self.max_width,
                self.max_height,
                self.unknown_0c,
                table_offset,
                total_entries,
            )
        )

        # Write glyph table
        glyph_idx = 0
        for table_idx in range(total_entries):
            if table_idx in dup_set:
                source_glyph_idx = dup_map[table_idx]
                char_code = self.glyphs[source_glyph_idx].char_code
                offset = glyph_offsets[source_glyph_idx]
            else:
                char_code = self.glyphs[glyph_idx].char_code
                offset = glyph_offsets[glyph_idx]
                glyph_idx += 1
            buf.write(struct.pack("<II", char_code, offset))

        # Write glyph data
        for blob in glyph_data_blobs:
            buf.write(blob)

        return buf.getvalue()

    def to_file(self, path: Path) -> None:
        # Write MGS font to file.
        path.write_bytes(self.to_bytes())

    def save_metadata(self, path: Path) -> None:
        # Save font metadata as JSON (for round-trip reconstruction).
        glyph_metas = []
        for glyph in self.glyphs:
            meta = {
                "char_code": glyph.char_code,
                "width": glyph.width,
                "height": glyph.height,
                "bearing_x": glyph.bearing_x,
                "bearing_y": glyph.bearing_y,
                "advance": glyph.advance,
            }
            glyph_metas.append(meta)

        meta = {
            "max_width": self.max_width,
            "max_height": self.max_height,
            "unknown_0c": self.unknown_0c,
            "glyph_count": len(self.glyphs),
            "duplicate_indices": self.duplicate_indices,
            "glyphs": glyph_metas,
        }
        path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def from_exported(cls, folder: Path) -> "MgsFont":
        # Create an MgsFont from a previously exported folder (images + metadata).
        meta_path = folder / "mgs_font.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {meta_path}")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        max_width = meta["max_width"]
        max_height = meta["max_height"]
        unknown_0c = meta["unknown_0c"]
        duplicate_indices = [tuple(d) for d in meta.get("duplicate_indices", [])]

        images_dir = folder / "glyphs"
        glyphs: list[MgsGlyph] = []

        for glyph_meta in meta["glyphs"]:
            char_code = glyph_meta["char_code"]
            width = glyph_meta["width"]
            height = glyph_meta["height"]
            bearing_x = glyph_meta["bearing_x"]
            bearing_y = glyph_meta["bearing_y"]
            advance = glyph_meta["advance"]

            pixel_data = b""
            if width > 0 and height > 0:
                image_path = images_dir / f"U+{char_code:04X}.png"
                if image_path.exists():
                    img = Image.open(image_path).convert("L")
                    # Allow the image to override dimensions
                    width = img.width
                    height = img.height
                    pixel_data = img.tobytes()
                else:
                    # Generate empty pixel data if image is missing
                    pixel_data = b"\x00" * (width * height)

            glyphs.append(
                MgsGlyph(
                    char_code=char_code,
                    width=width,
                    height=height,
                    bearing_x=bearing_x,
                    bearing_y=bearing_y,
                    advance=advance,
                    pixel_data=pixel_data,
                )
            )

        return cls(
            max_width=max_width,
            max_height=max_height,
            unknown_0c=unknown_0c,
            glyphs=glyphs,
            duplicate_indices=duplicate_indices,
        )


def export_mgs_font(input_file: Path, output_dir: Path) -> None:
    # Export an MGS font file to a folder with glyph images + metadata JSON.
    typer.echo(f"Exporting {input_file} to {output_dir}...")

    font = MgsFont.from_file(input_file)

    typer.echo(f"Max glyph size: {font.max_width}x{font.max_height}")
    typer.echo(
        f"Glyphs: {len(font.glyphs)} unique, {len(font.duplicate_indices)} duplicates"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "glyphs"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Save metadata
    meta_path = output_dir / "mgs_font.json"
    font.save_metadata(meta_path)
    typer.echo(f"Metadata saved to {meta_path}")

    # Save glyph images
    saved = 0
    for glyph in font.glyphs:
        img = glyph.to_image()
        if img is not None:
            img_path = images_dir / f"U+{glyph.char_code:04X}.png"
            img.save(img_path)
            saved += 1

    typer.echo(f"Saved {saved} glyph images to {images_dir}")


def import_mgs_font(input_dir: Path, output_file: Path) -> None:
    # Import glyph images + metadata back into an MGS font file.
    typer.echo(f"Importing from {input_dir}...")

    font = MgsFont.from_exported(input_dir)
    font.to_file(output_file)

    typer.echo(f"Written to {output_file}")
