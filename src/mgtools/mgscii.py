MGSCII_TABLE = {
    10: "\n",
    32: " ",
    33: "!",
    34: '"',
    35: "#",
    36: "$",
    37: "%",
    38: "&",
    39: "'",
    40: "(",
    41: ")",
    42: "*",
    43: "+",
    44: ",",
    45: "-",
    46: ".",
    47: "/",
    48: "0",
    49: "1",
    50: "2",
    51: "3",
    52: "4",
    53: "5",
    54: "6",
    55: "7",
    56: "8",
    57: "9",
    58: ":",
    59: ";",
    60: "<",
    61: "=",
    62: ">",
    63: "?",
    64: "@",
    65: "A",
    66: "B",
    67: "C",
    68: "D",
    69: "E",
    70: "F",
    71: "G",
    72: "H",
    73: "I",
    74: "J",
    75: "K",
    76: "L",
    77: "M",
    78: "N",
    79: "O",
    80: "P",
    81: "Q",
    82: "R",
    83: "S",
    84: "T",
    85: "U",
    86: "V",
    87: "W",
    88: "X",
    89: "Y",
    90: "Z",
    91: "[",
    92: "\\",
    93: "]",
    94: "^",
    95: "_",
    96: "`",
    97: "a",
    98: "b",
    99: "c",
    100: "d",
    101: "e",
    102: "f",
    103: "g",
    104: "h",
    105: "i",
    106: "j",
    107: "k",
    108: "l",
    109: "m",
    110: "n",
    111: "o",
    112: "p",
    113: "q",
    114: "r",
    115: "s",
    116: "t",
    117: "u",
    118: "v",
    119: "w",
    120: "x",
    121: "y",
    122: "z",
    123: "{",
    124: "|",
    125: "}",
    126: "~",
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
    8230: "…",
    8734: "∞",
}

SPECIAL_CHARS = {99: "…", 135: "∞"}


def get_mgscii_char(code: int) -> str:
    return MGSCII_TABLE.get(code, "???")


def read_mgscii_string(data: bytes) -> str:
    return_str = ""

    special_char_parsed = False
    for byte in data:
        if byte != 129 and not special_char_parsed:
            return_str += get_mgscii_char(byte)
        elif byte == 129 and not special_char_parsed:
            special_char_parsed = True
        elif special_char_parsed:
            return_str += SPECIAL_CHARS.get(byte, "???")
            special_char_parsed = False

    return return_str


def write_mgscii_string(
    text: str, char_substition_map: dict[str, int] | None = None
) -> bytes:
    reverse_map = {v: k for k, v in MGSCII_TABLE.items()}
    special_chars_map = {v: k for k, v in SPECIAL_CHARS.items()}
    return_bytes = bytearray()

    for char in text:
        if char_substition_map and char in char_substition_map:
            c = char_substition_map[char]
        else:
            c = reverse_map.get(char)

        if c is None:
            c = 63  # 63 is the code for '?'

        if c > 255:
            if char in special_chars_map:
                return_bytes.append(129)
                return_bytes.append(special_chars_map[char])
        else:
            return_bytes.append(c)

    return return_bytes
