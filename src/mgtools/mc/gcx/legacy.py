"""The PS2 text encoding of the strings of GCX scripts, and its markup.

ASCII stands for itself and 0A breaks lines. 1F xx is an accented letter. A lead
byte from 80 starts a two-byte code whose low 5 bits name a page: 0 ASCII, 1
hiragana, 2 katakana, 3 symbols, and C and D the glyphs of the script. Its bits
40 and 20 are attributes, which the markup writes as U+E000 and U+E001 before
the character, as the Bluepoint texts do. The markup writes every code that has
no character of its own, and the braces, as their bytes in hex between braces,
such as {8C01} for the first glyph.
"""

import re
from collections.abc import Iterator

_LATIN = dict(
    zip(
        b"\x04\x06\x07\x08\x09\x0a\x0b\x0e\x0f\x10\x11\x13\x14\x15\x17\x18\x19\x1a"
        b"\x1b\x1d\x1f\x20\x28\x3c\x3d\x41\x42\x64\x6b",
        "ÉÖÜáàâäçéèêíìîñóòôöúûüßªº¿¡„Í",
        strict=True,
    )
)
_SYMBOLS = {
    0x01: "\u3000",
    0x02: "\ue081",
    0x03: "\ue083",
    0x04: "\ue082",
    0x05: "\ue080",
    0x07: "\uff1f",
    0x08: "\u3001",
    0x09: "\u3002",
    0x0B: "\u300f",
    0x12: "\u30fc",
    0x17: "\u300e",
}
_ATTRIBUTES = {0x40: "\ue000", 0x20: "\ue001"}
_ATTRIBUTE_BITS = {prefix: bit for bit, prefix in _ATTRIBUTES.items()}
_ASCII_PAGE = 0x80
# Glyph n of the script is code 8C n+1 up to the 255th, then 8D n-254.
_GLYPH_PAGES = {0x8C: 0, 0x8D: 255}
_PLAIN = frozenset(range(0x20, 0x7F)) - set(b"{}") | {0x0A}
_HEX_CODE = re.compile(r"\{((?:[0-9A-Fa-f]{2})+)\}")


def _kana(first: int) -> dict[int, str]:
    """Return a kana page of the PS2 encoding, from the Unicode block starting at first."""
    # The pages follow Unicode but skip its two obsolete letters before wo.
    page = {code: chr(first + code) for code in range(1, 0x50)}
    return page | {0x50: chr(first + 0x52), 0x51: chr(first + 0x53)}


_CHARACTERS = {
    bytes([lead, code]): character
    for lead, page in (
        (0x1F, _LATIN),
        (0x81, _kana(0x3040)),
        (0x82, _kana(0x30A0) | {0x52: "\u30f4"}),
        (0x83, _SYMBOLS),
    )
    for code, character in page.items()
}
_CODES = {character: code for code, character in _CHARACTERS.items()}


def decode_legacy(data: bytes) -> str:
    """Return the markup of a string in the PS2 encoding.

    Args:
        data: The string's bytes, without its terminating NUL.
    """
    return "".join(_markup(token) for token in _tokens(data))


def glyphs_used(data: bytes) -> int:
    """Return how many glyphs a string in the PS2 encoding needs, up to its last.

    Args:
        data: The string's bytes, without its terminating NUL.
    """
    return max(
        (
            _GLYPH_PAGES[token[0]] + token[1]
            for token in _tokens(data)
            if len(token) == 2 and token[0] in _GLYPH_PAGES
        ),
        default=0,
    )


def encode_legacy(markup: str) -> bytes:
    """Return the PS2 encoding of a string's markup.

    Args:
        markup: The string as decode_legacy writes it.
    """
    data = bytearray()
    attributes = 0
    position = 0
    while position < len(markup):
        character = markup[position]
        if bit := _ATTRIBUTE_BITS.get(character):
            attributes |= bit
            position += 1
        elif character == "{" and not attributes:
            code = _HEX_CODE.match(markup, position)
            if code is None:
                msg = f"The {{ at {position} does not start a hex code such as {{8C01}}"
                raise ValueError(msg)
            data += bytes.fromhex(code[1])
            position = code.end()
        else:
            data += _encode_character(character, attributes)
            attributes = 0
            position += 1
    if attributes:
        msg = "The text ends with an attribute, which needs a character after it"
        raise ValueError(msg)
    return bytes(data)


def _tokens(data: bytes) -> Iterator[bytes]:
    """Split a string into its codes of one or two bytes."""
    position = 0
    while position < len(data):
        size = 2 if data[position] == 0x1F or data[position] >= 0x80 else 1
        yield data[position : position + size]
        position += size


def _markup(token: bytes) -> str:
    """Return the markup of a code: its character, or its bytes in hex between braces."""
    if token[0] in _PLAIN:
        return chr(token[0])
    character = _character(token) if len(token) == 2 else None
    return character or f"{{{token.hex().upper()}}}"


def _character(pair: bytes) -> str | None:
    """Return a two-byte code's character after its attribute prefixes, or None."""
    lead, code = pair
    attributes = lead & 0x60 if lead >= 0x80 else 0
    character = _CHARACTERS.get(bytes([lead ^ attributes, code]))
    # Without attributes, page 0 cannot be told from plain ASCII in the texts.
    if character is None and attributes and lead ^ attributes == _ASCII_PAGE:
        character = chr(code) if 0x20 <= code < 0x7F else None
    if character is None:
        return None
    return "".join(_ATTRIBUTES[bit] for bit in _ATTRIBUTES if attributes & bit) + character


def _encode_character(character: str, attributes: int) -> bytes:
    """Return the code of a character, with the attribute bits in its lead byte."""
    printable = " " <= character <= "~"
    if not attributes and (printable or character == "\n"):
        return character.encode("ascii")
    code = _CODES.get(character)
    if code is None and attributes and printable:
        code = bytes([_ASCII_PAGE, ord(character)])
    if code is None:
        msg = f"{character!r} (U+{ord(character):04X}) has no code in the PS2 encoding"
        raise ValueError(msg)
    if attributes and code[0] < 0x80:
        msg = f"{character!r} cannot take an attribute"
        raise ValueError(msg)
    return bytes([code[0] | attributes, code[1]])
