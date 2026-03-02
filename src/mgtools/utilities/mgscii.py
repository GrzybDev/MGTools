_MGSCII_EXTENDED = {
    167: "č",
    168: "ě",
    169: "ů",
    170: "ř",
    171: "ý",
    172: "ž",
    176: "à",
    177: "á",
    178: "â",
    179: "ä",
    180: "À",
    181: "Á",
    182: "Â",
    183: "Ä",
    184: "è",
    185: "é",
    186: "ê",
    187: "ë",
    188: "È",
    189: "É",
    190: "Ê",
    191: "Ë",
    192: "ì",
    193: "í",
    194: "î",
    195: "ï",
    196: "Ì",
    197: "Í",
    198: "Î",
    199: "Ï",
    200: "ò",
    201: "ó",
    202: "ô",
    203: "ö",
    204: "Ò",
    205: "Ó",
    206: "Ô",
    207: "Ö",
    208: "ù",
    209: "ú",
    210: "û",
    211: "ü",
    212: "Ù",
    213: "Ú",
    214: "Û",
    215: "Ü",
    216: "ñ",
    217: "ç",
    218: "ß",
    219: "Ç",
    220: "¡",
    221: "¿",
    222: "®",
    223: "°",
}

_REVERSE_EXTENDED = {v: k for k, v in _MGSCII_EXTENDED.items()}


def _is_sjis_lead_byte(byte: int) -> bool:
    # Check if a byte is a Shift-JIS lead byte.
    return (0x81 <= byte <= 0x9F) or (0xE0 <= byte <= 0xFC)


def get_mgscii_char(code: int) -> str:
    if code in _MGSCII_EXTENDED:
        return _MGSCII_EXTENDED[code]

    try:
        return bytes([code]).decode("shift_jis")
    except (UnicodeDecodeError, ValueError):
        return "?"


def read_mgscii_string(data: bytes) -> str:
    return_str = ""
    i = 0

    while i < len(data):
        byte = data[i]

        if _is_sjis_lead_byte(byte) and i + 1 < len(data):
            # Try two-byte Shift-JIS decode
            pair = data[i : i + 2]
            try:
                return_str += pair.decode("shift_jis")
                i += 2
                continue
            except (UnicodeDecodeError, ValueError):
                pass

        return_str += get_mgscii_char(byte)
        i += 1

    return return_str


def write_mgscii_string(
    text: str, char_substitution_map: dict[str, int] | None = None
) -> bytes:
    return_bytes = bytearray()

    for char in text:
        if char_substitution_map and char in char_substitution_map:
            return_bytes.append(char_substitution_map[char])
            continue

        if char in _REVERSE_EXTENDED:
            return_bytes.append(_REVERSE_EXTENDED[char])
            continue

        # Fall back to Shift-JIS encoding (handles ASCII and multi-byte)
        try:
            return_bytes.extend(char.encode("shift_jis"))
        except (UnicodeEncodeError, ValueError):
            return_bytes.append(63)  # '?'

    return return_bytes
