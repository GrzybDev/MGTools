"""Strcode dictionaries: files of names for the listing to write instead of strcodes.

Each line holds a strcode in hex, as 0C4FAF, 0x0C4FAF or #0C4FAF, whitespace and
its name; words after the name are ignored and blank lines skipped. A listing
compiles a name back by hashing it, so only names that read back as names and
hash to their strcode are used; every other line is skipped with its reason.
"""

import re
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from mgtools.errors import located
from mgtools.mc.gcx.parser import is_name
from mgtools.mc.gcx.strcode import strcode

_CODE = re.compile(r"(?:0[xX]|#)?([0-9A-Fa-f]{1,6})")
# Names are ASCII, which both read alike, so the order only decides how a skipped name
# shows. EUC-JP would read much UTF-8 text as other characters, so it comes second.
_ENCODINGS = ("utf-8-sig", "euc_jp")


@dataclass(frozen=True, slots=True)
class Dictionary:
    names: dict[int, str]
    """The names a listing can write, by strcode."""
    skipped: dict[int, str]
    """Why each line that is not used was skipped, by line number from 1."""


def read_dictionary(path: Path) -> Dictionary:
    """Read the names of a dictionary that a listing can hold, skipping the other lines.

    Args:
        path: The dictionary file to read.
    """
    with located(path):
        text = _text(path.read_bytes())
    names: dict[int, str] = {}
    skipped: dict[int, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            code, name = _entry(line)
        except ValueError as error:
            skipped[number] = str(error)
            continue
        if names.setdefault(code, name) != name:
            skipped[number] = f"#{code:06X} already has the name {names[code]}"
    return Dictionary(names, skipped)


def _text(data: bytes) -> str:
    """Return the text of a dictionary in the first of its encodings that reads it."""
    for encoding in _ENCODINGS:
        with suppress(UnicodeDecodeError):
            return data.decode(encoding)
    msg = "not UTF-8 or EUC-JP text"
    raise ValueError(msg)


def _entry(line: str) -> tuple[int, str]:
    """Return the strcode and name of a line, raising the reason a listing cannot use it."""
    # A name holds no whitespace, so the words after it, such as a comment column, never
    # reach the listing and cannot change what it compiles to.
    words = line.split()
    if len(words) < 2:
        msg = f"expected a strcode in hex and a name, found {line.strip()!r}"
        raise ValueError(msg)
    hex_code, name = words[:2]
    if not (match := _CODE.fullmatch(hex_code)):
        msg = f"{hex_code!r} is not a strcode of up to six hex digits"
        raise ValueError(msg)
    if not is_name(name):
        msg = f"{name!r} is not a name: ASCII letters, digits and _, not starting with a digit"
        raise ValueError(msg)
    code = int(match[1], 16)
    if (hashed := strcode(name)) != code:
        msg = f"{name} hashes to #{hashed:06X}, not #{code:06X}"
        raise ValueError(msg)
    return code, name
