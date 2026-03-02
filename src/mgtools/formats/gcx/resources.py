from mgtools.formats.gcx.nodes import GcxFile


def get_resource_data(gcx: GcxFile, index: int) -> bytes:
    """Get the decrypted data for a resource by index."""
    if index >= len(gcx.resource_entries):
        raise IndexError(f"Resource index {index} out of range")

    offset = gcx.resource_entries[index] & 0x00FFFFFF

    # Determine end offset
    if index + 1 < len(gcx.resource_entries):
        end_offset = gcx.resource_entries[index + 1] & 0x00FFFFFF
    else:
        end_offset = len(gcx.string_data)

    return gcx.string_data[offset:end_offset]


def is_script_resource(entry: int) -> bool:
    """Check if a resource table entry refers to a script resource."""
    return (entry & 0xFF000000) != 0x80000000


def escape_resource_bytes(data: bytes) -> str:
    """Convert raw resource bytes to a human-readable escaped string.

    Printable ASCII is kept as-is.  Special cases:
    - ``\\n``  for 0x0A (newline)
    - ``\\\\`` for 0x5C (backslash)
    - ``\\xHH`` for everything else non-printable (including NUL)

    The encoding is byte-exact: no bytes are stripped or added.
    """
    parts: list[str] = []
    for b in data:
        if b == 0x0A:
            parts.append("\\n")
        elif b == 0x5C:
            parts.append("\\\\")
        elif 0x20 <= b < 0x7F:
            parts.append(chr(b))
        else:
            parts.append(f"\\x{b:02X}")
    return "".join(parts)


def unescape_resource_text(text: str) -> bytes:
    """Parse an escaped resource string back to raw bytes.

    Inverse of :func:`escape_resource_bytes`.  The conversion is byte-exact:
    no extra bytes are added.
    """
    result = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nc = text[i + 1]
            if nc == "n":
                result.append(0x0A)
                i += 2
            elif nc == "\\":
                result.append(0x5C)
                i += 2
            elif nc == "x" and i + 3 < len(text):
                result.append(int(text[i + 2 : i + 4], 16))
                i += 4
            else:
                result.append(ord(text[i]))
                i += 1
        else:
            result.append(ord(text[i]))
            i += 1
    return bytes(result)
