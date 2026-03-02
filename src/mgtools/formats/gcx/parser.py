import struct
from pathlib import Path

from mgtools.formats.gcx.cipher import decrypt_data, encrypt_data
from mgtools.formats.gcx.nodes import GcxFile
from mgtools.formats.gcx.reader import Reader
from mgtools.formats.gcx.writer import Writer


class Gcx:
    """Main GCX class for parsing and compiling GCX files. Provides high-level APIs to convert between GcxFile objects and raw bytes or disk files."""

    LCGB_MAGIC = b"LCGB"

    @classmethod
    def from_file(cls, path: Path) -> GcxFile:
        """Parse a GCX file from disk."""
        data = path.read_bytes()
        return cls.from_bytes(data)

    @classmethod
    def from_bytes(cls, data: bytes) -> GcxFile:
        """Parse GCX from raw bytes."""
        r = Reader(data)

        # Check for LCGB header
        has_lcgb = data[:4] == cls.LCGB_MAGIC
        if has_lcgb:
            r.pos = 4

        # Timestamp
        timestamp = r.u32()

        # Proc table (u32 offsets terminated by 0xFFFFFFFF)
        proc_offsets: list[int] = []
        while True:
            val = r.u32()
            if val == 0xFFFFFFFF:
                break
            proc_offsets.append(val)

        # Block header
        block_start = r.pos
        proc_offset = r.u32()
        resource_table_offset = r.u32()
        string_resources_offset = r.u32()
        font_data_offset = r.u32()
        seed = r.u32()

        # Extra data between block header and resource table (blueprint data)
        header_end_abs = block_start + 20  # 5 * u32
        res_table_abs = block_start + resource_table_offset
        extra_data = data[header_end_abs:res_table_abs]

        string_data_abs = block_start + string_resources_offset
        font_data_abs = block_start + font_data_offset

        num_resources = (string_resources_offset - resource_table_offset) // 4
        resource_entries = []
        for i in range(num_resources):
            resource_entries.append(
                struct.unpack_from("<I", data, res_table_abs + i * 4)[0]
            )

        # String/resource data (decrypt if needed)
        raw_string_data = data[string_data_abs:font_data_abs]
        string_data = decrypt_data(seed, raw_string_data)

        # Font data
        script_abs = block_start + proc_offset
        font_data = data[font_data_abs:script_abs]

        # Script sections
        proc_body_size = struct.unpack_from("<I", data, script_abs)[0]
        proc_body_start = script_abs + 4
        proc_body_data = data[proc_body_start : proc_body_start + proc_body_size]

        main_body_offset = proc_body_start + proc_body_size
        main_body_size = struct.unpack_from("<I", data, main_body_offset)[0]
        main_body_start = main_body_offset + 4
        main_body_data = data[main_body_start : main_body_start + main_body_size]

        # Trailing data after main body (padding)
        trailing_data = data[main_body_start + main_body_size :]

        return GcxFile(
            has_lcgb_header=has_lcgb,
            timestamp=timestamp,
            proc_offsets=proc_offsets,
            proc_offset=proc_offset,
            resource_table_offset=resource_table_offset,
            string_resources_offset=string_resources_offset,
            font_data_offset=font_data_offset,
            seed=seed,
            resource_entries=resource_entries,
            extra_data=extra_data,
            string_data=string_data,
            font_data=font_data,
            proc_body_data=proc_body_data,
            main_body_data=main_body_data,
            trailing_data=trailing_data,
        )

    @classmethod
    def to_bytes(cls, gcx: GcxFile) -> bytes:
        """Compile a GcxFile back to binary."""
        w = Writer()

        # LCGB header
        if gcx.has_lcgb_header:
            w.write(cls.LCGB_MAGIC)

        # Timestamp
        w.u32(gcx.timestamp)

        # Proc table
        for offset in gcx.proc_offsets:
            w.u32(offset)
        w.u32(0xFFFFFFFF)

        block_start = w.tell()

        # We'll write placeholder block header, then fill it in
        header_pos = w.tell()
        w.u32(0)  # proc_offset placeholder
        w.u32(0)  # resource_table_offset placeholder
        w.u32(0)  # string_resources_offset placeholder
        w.u32(0)  # font_data_offset placeholder
        w.u32(gcx.seed)

        # Extra data (blueprint data, preserved from original)
        if gcx.extra_data:
            w.write(gcx.extra_data)

        # Resource table
        res_table_offset = w.tell() - block_start
        for entry in gcx.resource_entries:
            w.u32(entry)

        # String/resource data (encrypt if needed)
        string_data_offset = w.tell() - block_start
        encrypted = encrypt_data(gcx.seed, gcx.string_data)
        w.write(encrypted)

        # Font data
        font_data_offset = w.tell() - block_start
        w.write(gcx.font_data)

        # Script: proc body
        proc_offset = w.tell() - block_start
        w.u32(len(gcx.proc_body_data))
        w.write(gcx.proc_body_data)

        # Script: main body
        w.u32(len(gcx.main_body_data))
        w.write(gcx.main_body_data)

        # Trailing padding
        if gcx.trailing_data:
            w.write(gcx.trailing_data)

        # Patch the block header
        result = bytearray(w.getvalue())
        struct.pack_into("<I", result, header_pos, proc_offset)
        struct.pack_into("<I", result, header_pos + 4, res_table_offset)
        struct.pack_into("<I", result, header_pos + 8, string_data_offset)
        struct.pack_into("<I", result, header_pos + 12, font_data_offset)

        return bytes(result)

    @classmethod
    def to_file(cls, gcx: GcxFile, path: Path):
        """Write a GcxFile to disk."""
        path.write_bytes(cls.to_bytes(gcx))
