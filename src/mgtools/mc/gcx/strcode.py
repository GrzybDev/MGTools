"""The 24-bit name hash of GCL scripts, manifests and la2 files."""


def strcode(name: str) -> int:
    """Return the hash of an ASCII name, never 0: a name hashing to 0 gets 1.

    Args:
        name: The name of a command, stage or other thing the scripts refer to.
    """
    code = 0
    for byte in name.encode("ascii"):
        code = ((code >> 19) | (code << 5)) & 0xFFFFFF
        code = (code + byte) & 0xFFFFFF
    return code or 1
