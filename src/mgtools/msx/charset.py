"""The characters of the MSX games' texts and the bytes that store them.

0x0A breaks a line and 0x20 to 0x7E are ASCII. Of the other single bytes, every
engine routine reads only 0x7F and 0xA0 to 0xDF as one character, so a charmap
names the characters the font draws there. A Shift-JIS lead byte and a trail
byte make a double-byte character. Engine codes read as placeholders such as
{wait}; bytes that are no character read as {x:HH} or {sjis:HHHH}, so any bytes
read back the same.
"""

import re
from collections.abc import Iterator

from mgtools.msx.game import Game

type Charmap = dict[int, str]

# Every other byte from 0x80 up is a lead byte to some engine routine.
_FREE_CODES = frozenset((0x7F, *range(0xA0, 0xE0)))

EU_CHARMAP: Charmap = {
    0xA7: "č", 0xA8: "ě", 0xA9: "ů", 0xAA: "ř", 0xAB: "ý", 0xAC: "ž", 0xAD: "„",
    0xB0: "à", 0xB1: "á", 0xB2: "â", 0xB3: "ä", 0xB4: "À", 0xB5: "Á", 0xB6: "Â",
    0xB7: "Ä", 0xB8: "è", 0xB9: "é", 0xBA: "ê", 0xBB: "ë", 0xBC: "È", 0xBD: "É",
    0xBE: "Ê", 0xBF: "Ë", 0xC0: "ì", 0xC1: "í", 0xC2: "î", 0xC3: "ï", 0xC4: "Ì",
    0xC5: "Í", 0xC6: "Î", 0xC7: "Ï", 0xC8: "ò", 0xC9: "ó", 0xCA: "ô", 0xCB: "ö",
    0xCC: "Ò", 0xCD: "Ó", 0xCE: "Ô", 0xCF: "Ö", 0xD0: "ù", 0xD1: "ú", 0xD2: "û",
    0xD3: "ü", 0xD4: "Ù", 0xD5: "Ú", 0xD6: "Û", 0xD7: "Ü", 0xD8: "ñ", 0xD9: "ç",
    0xDA: "ß", 0xDB: "Ç", 0xDC: "¡", 0xDD: "¿", 0xDE: "®", 0xDF: "°",
}  # fmt: skip
"""The characters the fonts of the European releases draw."""

JP_CHARMAP: Charmap = {
    0xB1: "á", 0xB2: "č", 0xB3: "ě", 0xB4: "í", 0xB5: "ú", 0xB6: "ů", 0xB7: "ř",
    0xB8: "ý", 0xB9: "ž",
}  # fmt: skip
"""The characters the Japanese font draws, for the lines Marv speaks in Czech."""

_MG2_ESCAPES = {
    b"w": "{wait}",
    b"W": "{autowait}",
    b"r": "{r}",
    b"s": "{s}",
    b"e": "{e}",
    b"f": "{f}",
    **{str(n).encode(): f"{{speed:{n}}}" for n in range(1, 10)},
}
_MG2_COMMANDS = {b"B": "bgm", b"S": "se"}
_MG2_ESCAPE_CODES = {text: b"\\" + code for code, text in _MG2_ESCAPES.items()}
_MG2_COMMAND_CODES = {name: b"\\" + code for code, name in _MG2_COMMANDS.items()}
_PLACEHOLDER = re.compile(r"\{([a-z]+)(?::([^{}]*))?\}")
_COMMAND_ARGUMENT = re.compile("[ -z|~]{2}")
_ARGUMENTS = {
    "bgm": _COMMAND_ARGUMENT,
    "se": _COMMAND_ARGUMENT,
    "btn": re.compile("[0-9]"),
    "x": re.compile("[0-9A-Fa-f]{2}"),
    "sjis": re.compile("[0-9A-Fa-f]{4}"),
}


def _is_lead(byte: int) -> bool:
    """Tell whether a byte can start a Shift-JIS double-byte character."""
    return 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xFC


def _is_trail(byte: int) -> bool:
    """Tell whether a byte can end a Shift-JIS double-byte character."""
    return 0x40 <= byte <= 0x7E or 0x80 <= byte <= 0xFC


def character_codes(charmap: Charmap) -> dict[str, int]:
    """Return the code of each character a charmap names, refusing codes not free.

    Args:
        charmap: The characters to give single-byte codes, by code.
    """
    codes: dict[str, int] = {}
    for code, character in charmap.items():
        if code not in _FREE_CODES:
            msg = f"The charmap names {code:02X}, but only 7F and A0 to DF are free"
            raise ValueError(msg)
        if len(character) != 1 or ord(character) < 0xA0:
            msg = f"The charmap gives {code:02X} {character!r}, not a new character"
            raise ValueError(msg)
        if character in codes:
            msg = f"The charmap gives {character!r} to two codes"
            raise ValueError(msg)
        codes[character] = code
    return codes


class Charset:
    """Reads and writes the texts of a game with the characters of a charmap."""

    def __init__(self, game: Game, charmap: Charmap) -> None:
        """Use a charmap for the texts of a game, refusing a charmap that is not valid.

        Args:
            game: The game of the texts, which decides their engine codes.
            charmap: The characters the font draws at single-byte codes.
        """
        self.game = game
        self.charmap = charmap
        self._codes = character_codes(charmap)

    def decode(self, data: bytes) -> str:
        """Return the text of some bytes.

        Args:
            data: The bytes of a text.
        """
        return "".join(text for _, text in self.characters(data))

    def characters(self, data: bytes) -> Iterator[tuple[bytes, str]]:
        """Yield the bytes and the text of each character or engine code.

        Args:
            data: The bytes of a text.
        """
        position = 0
        while position < len(data):
            size, text = self._character(data, position)
            yield data[position : position + size], text
            position += size

    def _character(self, data: bytes, position: int) -> tuple[int, str]:
        """Return the size and the text of the character or engine code at position."""
        byte, following = data[position], data[position + 1 : position + 4]
        if _is_lead(byte) and following and _is_trail(following[0]):
            return 2, self._double_byte(data[position : position + 2])
        if byte == 0x5C and self.game is Game.MG2:
            if text := _MG2_ESCAPES.get(following[:1]):
                return 2, text
            command = _MG2_COMMANDS.get(following[:1])
            argument = following[1:].decode("latin-1")
            if command and _COMMAND_ARGUMENT.fullmatch(argument):
                return 4, f"{{{command}:{argument}}}"
        elif byte == 0x7C and following[:1].isdigit():
            return 2, f"{{btn:{following[:1].decode()}}}"
        elif byte == 0x0A or (0x20 <= byte <= 0x7E and byte not in b"{}"):
            return 1, chr(byte)
        elif byte in self.charmap:
            return 1, self.charmap[byte]
        return 1, f"{{x:{byte:02X}}}"

    def _double_byte(self, pair: bytes) -> str:
        """Return the character of a double-byte code, or a placeholder if it encodes otherwise."""
        try:
            character = pair.decode("cp932")
            # Keep the code of a character that has a single byte or another code.
            if character not in self._codes and character.encode("cp932") == pair:
                return character
        except UnicodeError:
            pass
        return f"{{sjis:{pair.hex().upper()}}}"

    def encode(self, text: str) -> bytes:
        """Return the bytes of a text, refusing what the game cannot store.

        Args:
            text: The text to encode, with its placeholders.
        """
        data = bytearray()
        position = 0
        while position < len(text):
            if text[position] == "{":
                if not (match := _PLACEHOLDER.match(text, position)):
                    start = text[position : position + 12]
                    msg = f"The {{ of {start!r} opens no placeholder"
                    raise ValueError(msg)
                data += self._placeholder(match[0], match[1], match[2])
                position = match.end()
            else:
                data += self._encode_character(text[position])
                position += 1
        return bytes(data)

    def _placeholder(self, text: str, name: str, argument: str | None) -> bytes:
        """Return the bytes of a placeholder, refusing one the game does not have."""
        argument = argument or ""
        valid = name in _ARGUMENTS and _ARGUMENTS[name].fullmatch(argument)
        mg2 = self.game is Game.MG2
        match name:
            case _ if mg2 and text in _MG2_ESCAPE_CODES:
                return _MG2_ESCAPE_CODES[text]
            case "bgm" | "se" if mg2 and valid:
                return _MG2_COMMAND_CODES[name] + argument.encode()
            case "btn" if valid:
                return b"|" + argument.encode()
            case "x" | "sjis" if valid:
                return bytes.fromhex(argument)
        msg = f"{text} is not a placeholder of {self.game.upper()}"
        raise ValueError(msg)

    def _encode_character(self, character: str) -> bytes:
        if character == "}":
            msg = "A } closes no placeholder"
            raise ValueError(msg)
        if character == "\\" and self.game is Game.MG2:
            msg = "A backslash starts an engine code in MG2: use the placeholders"
            raise ValueError(msg)
        if character == "\n" or " " <= character <= "~":
            return character.encode()
        if (code := self._codes.get(character)) is not None:
            return bytes((code,))
        try:
            encoded = character.encode("cp932")
        except UnicodeEncodeError:
            encoded = b""
        if len(encoded) == 2:
            return encoded
        msg = (
            f"{character!r} (U+{ord(character):04X}) has no code: name it in the "
            "charmap of font.json and draw its glyph"
        )
        raise ValueError(msg)
