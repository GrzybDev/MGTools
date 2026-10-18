"""The engine's string tables: EngineSupport/stovc.bin and stovk.bin.

A table is XORed with an MT19937 keystream whose seed hashes the file's name up to
its first dot. Decrypted, it is little-endian: the size of the table (u64), the
table, an id (u32), a language (u32) and the start and end offsets (u64) of a
string per entry, sorted by id; then the strings, UTF-8 and NUL-terminated, back
to back in table order. Line breaks are CRLF.
"""

import random
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from mgtools.binary import BinaryReader, BinaryWriter
from mgtools.errors import FormatError
from mgtools.fileio import write_atomically
from mgtools.translation import TranslationFormat, Unit, export_units, read_document

# By their number in the table; the engine keeps the strings of "all" and of the
# language it runs in.
_LANGUAGES = ("all", "jp", "en", "fr", "it", "gr", "sp")
_TABLES = ("stovc", "stovk")
"""The names of the game's tables up to their first dot, which are their keys."""
_ENTRY = "IIQQ"
_ENTRY_SIZE = 24
_UNIT_ID = re.compile(r"([0-9a-f]{8})\.([a-z]+)")


@dataclass(frozen=True, slots=True)
class StovString:
    """A string of a table: its id, the language it is for and its text."""

    id: int
    language: str
    text: str


def decode_stov(data: bytes, name: str) -> list[StovString]:
    """Decrypt and read a table, given the name of its file.

    Args:
        data: The contents of the table's file.
        name: The name or path of the file, whose name up to its first dot is the key.
    """
    plain = _crypt(data, name)
    reader = BinaryReader(plain)
    size = reader.u64()
    if size > reader.remaining:
        msg = (
            f"Cannot decrypt {Path(name).name}: a string table decrypts only under "
            "its own name, stovc.bin or stovk.bin"
        )
        raise FormatError(msg)
    count, rest = divmod(size, _ENTRY_SIZE)
    if rest:
        msg = f"The table takes {size} bytes, not a multiple of {_ENTRY_SIZE}"
        raise FormatError(msg)
    entries = list(reader.iter_unpack(_ENTRY, count))
    pool = plain[reader.position :]
    strings: list[StovString] = []
    position = 0
    for string_id, language, start, end in entries:
        if strings and string_id <= strings[-1].id:
            msg = f"String {string_id:08x} follows {strings[-1].id:08x} out of id order"
            raise FormatError(msg)
        raw = pool[start:end]
        if start != position or len(raw) != end - start:
            msg = f"String {string_id:08x} is not stored right after the one before it"
            raise FormatError(msg)
        text, terminator, after = raw.partition(b"\0")
        if not terminator or after:
            msg = f"String {string_id:08x} does not end with its only NUL byte"
            raise FormatError(msg)
        if language >= len(_LANGUAGES):
            msg = f"String {string_id:08x} has the unknown language {language}"
            raise FormatError(msg)
        try:
            strings.append(StovString(string_id, _LANGUAGES[language], text.decode()))
        except UnicodeDecodeError as error:
            msg = f"String {string_id:08x} is not UTF-8: {error}"
            raise FormatError(msg) from error
        position = end
    if position != len(pool):
        msg = f"{len(pool) - position} bytes follow the last string"
        raise FormatError(msg)
    return strings


def encode_stov(strings: Iterable[StovString], name: str) -> bytes:
    """Build and encrypt a table for the file of the given name, sorted by id.

    Args:
        strings: The strings of the table, in any order.
        name: The name or path of the file, stovc.bin or stovk.bin.
    """
    if (key := _key(name)) not in _TABLES:
        msg = (
            f"The game reads only the tables stovc.bin and stovk.bin, whose names "
            f"are their keys, so a table named {key} would be unreadable"
        )
        raise ValueError(msg)
    strings = sorted(strings, key=lambda string: string.id)
    table, pool = BinaryWriter(), bytearray()
    table.u64(_ENTRY_SIZE * len(strings))
    for index, string in enumerate(strings):
        if index and string.id == strings[index - 1].id:
            msg = f"Two strings have the id {string.id:08x}"
            raise ValueError(msg)
        if "\0" in string.text:
            msg = f"String {string.id:08x} holds a NUL character"
            raise ValueError(msg)
        start = len(pool)
        pool += string.text.encode() + b"\0"
        table.pack(_ENTRY, string.id, _LANGUAGES.index(string.language), start, len(pool))
    table.write(pool)
    return _crypt(table.getvalue(), name)


def export_stov(
    strings: Iterable[StovString], path: Path, fmt: TranslationFormat, original: str
) -> None:
    """Write the strings of a table as a translation document of units such as 000e66b2.en.

    Args:
        strings: The strings of the table.
        path: The translation document to write.
        fmt: The format of the document.
        original: The name of the table's file, which the document records.
    """
    units = [
        Unit(f"{string.id:08x}.{string.language}", string.text.replace("\r\n", "\n"))
        for string in strings
    ]
    # The units mix the table's languages; translators start from the English ones.
    document = export_units(units, fmt, original=original, source_language="en")
    write_atomically(path, document)


def import_stov(path: Path) -> list[StovString]:
    """Read the strings back from a translation document, with CRLF line breaks.

    Args:
        path: The translation document export_stov wrote, translated or not.
    """
    strings = []
    for unit_id, text in read_document(path).items():
        match = _UNIT_ID.fullmatch(unit_id)
        if not match or match[2] not in _LANGUAGES:
            msg = f"{path}: {unit_id!r} is not a unit id such as 000e66b2.en"
            raise ValueError(msg)
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        strings.append(StovString(int(match[1], 16), match[2], text))
    return strings


def _crypt(data: bytes, name: str) -> bytes:
    """XOR data with the keystream of the file name, which encrypts and decrypts."""
    words = (len(data) + 3) // 4
    stream = _keystream(_seed(name)).getrandbits(32 * words).to_bytes(4 * words, "little")
    mask = int.from_bytes(stream[: len(data)], "little")
    return (int.from_bytes(data, "little") ^ mask).to_bytes(len(data), "little")


def _key(name: str) -> str:
    """Return the key of a table: the name of its file up to the first dot."""
    return Path(name).name.split(".")[0]


def _seed(name: str) -> int:
    """Return the keystream seed, a hash of the key of a table's file name."""
    seed = 0
    for byte in _key(name).encode():
        seed = (seed * 0x2356F + byte * 0x1D35) & 0xFFFF_FFFF
    return seed


def _keystream(seed: int) -> random.Random:
    """Return MT19937 seeded as the engine does, with the original 1998 sgenrand."""
    state = []
    for _ in range(624):
        high = seed & 0xFFFF_0000
        seed = (69069 * seed + 1) & 0xFFFF_FFFF
        state.append(high | seed >> 16)
        seed = (69069 * seed + 1) & 0xFFFF_FFFF
    generator = random.Random()
    generator.setstate((3, (*state, 624), None))
    return generator
