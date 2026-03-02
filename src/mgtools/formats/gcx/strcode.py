def strcode(name: str) -> int:
    """Compute the 24-bit GCL hash for *name*."""
    mask = 0x00FFFFFF
    h = 0
    for c in name.encode("ascii"):
        h = ((h >> 19) | (h << 5)) & mask
        h = (h + c) & mask
    return h if h else 1
