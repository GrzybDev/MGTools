def decrypt_data(seed: int, data: bytes) -> bytes:
    """Decrypt string resources using the LCG cipher."""
    if seed == 0 or len(data) == 0:
        return data
    out = bytearray(data)
    s = seed
    for i in range(len(out)):
        s = (s * 0x7D2B89DD + 0xCF9) & 0xFFFFFFFF
        out[i] ^= (s >> 15) & 0xFF
    return bytes(out)


def encrypt_data(seed: int, data: bytes) -> bytes:
    """Encrypt string resources – same operation as decrypt (XOR)."""
    return decrypt_data(seed, data)
