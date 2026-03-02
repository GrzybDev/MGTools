import struct
from dataclasses import dataclass

EMPTY_ENTRY = 0xFFFFFFFF


@dataclass
class BlueprintData:
    """Decoded blueprint (extra_data) block."""

    group_offsets: list[int]  # byte offsets for group boundaries [h0, h1]
    prefix: bytes  # 4-byte prefix before the first string
    strings: list[str | None]  # indexed strings (None = empty slot)
    trailing_strings: list[str]  # strings after the last table entry


def parse_blueprint(data: bytes) -> BlueprintData:
    """Parse raw extra_data bytes into a :class:`BlueprintData`."""
    if len(data) < 8:
        raise ValueError("Blueprint data too short")

    h0 = struct.unpack_from("<I", data, 0)[0]
    h1 = struct.unpack_from("<I", data, 4)[0]
    group_offsets = [h0, h1]

    # Read the offset table (from byte 8 to the first valid entry value).
    # First, find where the data region starts: it equals the first
    # non-0xFFFFFFFF entry value in the table.
    data_start: int | None = None
    for i in range(8, len(data), 4):
        v = struct.unpack_from("<I", data, i)[0]
        if v != EMPTY_ENTRY:
            data_start = v
            break

    if data_start is None:
        # All entries are empty – compute entry count from the full data
        num_entries = (len(data) - 8) // 4
        entries = [EMPTY_ENTRY] * num_entries
        return BlueprintData(
            group_offsets=group_offsets,
            prefix=b"\x00\x00\x00\x00",
            strings=[None] * num_entries,
            trailing_strings=[],
        )

    num_entries = (data_start - 8) // 4
    entries: list[int] = []
    for i in range(num_entries):
        entries.append(struct.unpack_from("<I", data, 8 + i * 4)[0])

    # 4-byte prefix
    prefix = data[data_start : data_start + 4]

    # Extract strings: each entry + 4 = start of the null-terminated string
    strings: list[str | None] = []
    for e in entries:
        if e == EMPTY_ENTRY:
            strings.append(None)
        else:
            s_start = e + 4
            s_end = s_start
            while s_end < len(data) and data[s_end] != 0:
                s_end += 1
            strings.append(data[s_start:s_end].decode("utf-8", errors="replace"))

    # Find trailing strings after the last table-referenced string
    last_valid = max((e for e in entries if e != EMPTY_ENTRY), default=None)
    trailing_strings: list[str] = []
    if last_valid is not None:
        s_start = last_valid + 4
        s_end = s_start
        while s_end < len(data) and data[s_end] != 0:
            s_end += 1
        # Skip past the null terminator of the last referenced string
        pos = s_end + 1
        while pos < len(data):
            s_end2 = pos
            while s_end2 < len(data) and data[s_end2] != 0:
                s_end2 += 1
            if s_end2 > pos:
                trailing_strings.append(
                    data[pos:s_end2].decode("utf-8", errors="replace")
                )
            pos = s_end2 + 1

    return BlueprintData(
        group_offsets=group_offsets,
        prefix=prefix,
        strings=strings,
        trailing_strings=trailing_strings,
    )


def build_blueprint(bp: BlueprintData) -> bytes:
    """Rebuild raw extra_data bytes from a :class:`BlueprintData`."""
    num_entries = len(bp.strings)
    has_any_string = any(s is not None for s in bp.strings) or bp.trailing_strings

    # Build string data first to compute offsets
    string_blobs: list[bytes] = []
    for s in bp.strings:
        if s is not None:
            string_blobs.append(s.encode("utf-8") + b"\x00")
        else:
            string_blobs.append(b"")  # placeholder, no data for null slots

    # Data area starts right after the header (2 u32) + offset table (N u32)
    table_size = 8 + num_entries * 4  # = data_start for first offset entry
    data_area_start = table_size

    # Lay out the string data sequentially
    # Only add prefix and string data when there are actual strings
    string_data = bytearray()
    if has_any_string:
        string_data.extend(bp.prefix)

    # Compute offset entries and build string data
    entries: list[int] = []
    for i, s in enumerate(bp.strings):
        if s is None:
            entries.append(EMPTY_ENTRY)
        else:
            if len(entries) == 0 or all(e == EMPTY_ENTRY for e in entries):
                # First valid entry: prefix occupies 4 bytes before string 0
                entry_offset = data_area_start + len(string_data) - 4
            else:
                # Subsequent entries: entry = position of string start – 4
                entry_offset = data_area_start + len(string_data) - 4

            entries.append(entry_offset)
            string_data.extend(string_blobs[i])

    # Trailing strings
    for ts in bp.trailing_strings:
        string_data.extend(ts.encode("utf-8") + b"\x00")

    # Build the binary
    result = bytearray()
    # Header: group offsets
    for go in bp.group_offsets:
        result.extend(struct.pack("<I", go))
    # Offset table
    for e in entries:
        result.extend(struct.pack("<I", e))
    # String data
    result.extend(string_data)

    return bytes(result)


def escape_blueprint_string(s: str) -> str:
    """Escape a blueprint string for display in GCL text.

    - Newlines become ``\\n``
    - Backslashes become ``\\\\``
    - Unicode private-use / control characters become ``\\uXXXX``
    """
    parts: list[str] = []
    for ch in s:
        if ch == "\n":
            parts.append("\\n")
        elif ch == "\\":
            parts.append("\\\\")
        elif ord(ch) < 0x20 or 0xE000 <= ord(ch) <= 0xF8FF:
            parts.append(f"\\u{ord(ch):04X}")
        else:
            parts.append(ch)
    return "".join(parts)


def unescape_blueprint_string(text: str) -> str:
    """Reverse of :func:`escape_blueprint_string`."""
    result: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nc = text[i + 1]
            if nc == "n":
                result.append("\n")
                i += 2
            elif nc == "\\":
                result.append("\\")
                i += 2
            elif nc == "u" and i + 5 < len(text):
                try:
                    code = int(text[i + 2 : i + 6], 16)
                    result.append(chr(code))
                    i += 6
                except ValueError:
                    result.append(text[i])
                    i += 1
            else:
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1
    return "".join(result)
