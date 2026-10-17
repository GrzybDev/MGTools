"""Exchanging translation units through Gettext PO.

A unit's id is its context and its notes are extracted comments. Lines are never
wrapped. Untranslated and fuzzy units keep their source text.
"""

from collections.abc import Iterable, Iterator

from translate.storage.pypo import pofile, pounit

from mgtools.errors import FormatError
from mgtools.translation.unit import Unit, collected


def export_po(units: Iterable[Unit], original: str) -> bytes:
    """Return a PO document with the units untranslated.

    Args:
        units: The texts to translate.
        original: The name of the file the units come from.
    """
    store = pofile(noheader=True, width=-1)
    store.init_headers(project_id_version=original, pot_creation_date="", po_revision_date="")
    for unit in units:
        if unit.source.startswith("_:"):
            msg = f"{unit.id!r} starts with _:, which PO reads as a comment"
            raise ValueError(msg)
        po_unit = store.UnitClass(unit.source, wrapper=store.wrapper)
        po_unit.setcontext(unit.id)
        for note in unit.notes:
            po_unit.addnote(note, origin="developer")
        store.addunit(po_unit)
    return bytes(store)


def import_po(data: bytes) -> dict[str, str]:
    """Return the text of each unit of a PO document by id.

    Args:
        data: The PO document.
    """
    try:
        store = pofile.parsestring(data)
    except ValueError as error:
        msg = f"Cannot read the PO document: {error}"
        raise FormatError(msg) from error
    return collected(_texts(store.units))


def _texts(units: Iterable[pounit]) -> Iterator[tuple[str, str]]:
    """Yield the id and text of each unit of a PO document but the header and obsolete ones."""
    for unit in units:
        if unit.isheader() or unit.isobsolete():
            continue
        unit_id = unit.getpreviouscontext()
        if not unit_id:
            msg = f"The unit {unit.source!r} has no context to take its id from"
            raise FormatError(msg)
        translated = unit.istranslated()
        # A tool may rewrap a source so that a line starts with _:, which is then
        # read as a KDE comment and cut from the source, but not from the target.
        if unit.msgidcomments and not translated:
            msg = f"{unit_id}: a line starting with _: was read as a comment"
            raise FormatError(msg)
        yield unit_id, str(unit.target if translated else unit.source)
