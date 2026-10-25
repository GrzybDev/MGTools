"""Translation units, and the texts translation documents can carry."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace

from mgtools.errors import FormatError

# XML 1.0 has no place for other control characters, for U+FFFE and U+FFFF or for
# lone surrogates; PO is held to the same set so that every format takes any unit.
_NOT_CARRIED = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
_ID = re.compile(r"[A-Za-z0-9._:-]+")
_PRIVATE_USE = re.compile("[\ue000-\uf8ff]")


@dataclass(frozen=True, slots=True)
class Unit:
    """A text to translate, named by an id unique in its document."""

    id: str
    source: str
    notes: tuple[str, ...] = ()


def checked(units: Iterable[Unit]) -> list[Unit]:
    """Return the units, refusing bad or repeated ids and characters no format holds.

    A unit whose source holds private-use characters gets a note naming them.

    Args:
        units: The units to check.
    """
    units = [_with_private_use_note(unit) for unit in units]
    ids: set[str] = set()
    for unit in units:
        if not _ID.fullmatch(unit.id):
            msg = f"The unit id {unit.id!r} is not letters, digits and . _ : -"
            raise ValueError(msg)
        if unit.id in ids:
            msg = f"Two units have the id {unit.id!r}"
            raise ValueError(msg)
        ids.add(unit.id)
        if match := _NOT_CARRIED.search("\n".join((unit.source, *unit.notes))):
            msg = (
                f"{unit.id!r} holds U+{ord(match[0]):04X}, which translation documents cannot carry"
            )
            raise ValueError(msg)
    return units


def _with_private_use_note(unit: Unit) -> Unit:
    """Name the private-use characters of a source, which tools may show as nothing."""
    codes = dict.fromkeys(f"U+{ord(c):04X}" for c in _PRIVATE_USE.findall(unit.source))
    if not codes:
        return unit
    note = "Keep its private-use characters, which tools may not show: "
    return replace(unit, notes=(*unit.notes, note + ", ".join(codes)))


def collected(texts: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Gather the texts of a document by unit id, refusing an id it repeats.

    Args:
        texts: The id and text of each unit, in document order.
    """
    by_id: dict[str, str] = {}
    for unit_id, text in texts:
        if unit_id in by_id:
            msg = f"The document has two units with the id {unit_id!r}"
            raise FormatError(msg)
        by_id[unit_id] = text
    return by_id
