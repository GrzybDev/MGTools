"""Exchanging translation units with translation tools: XLIFF 2.0, XLIFF 1.2 or PO."""

import codecs
from collections.abc import Collection, Iterable
from enum import StrEnum
from pathlib import Path

from mgtools.errors import located
from mgtools.translation.po import export_po, import_po
from mgtools.translation.unit import Unit, checked
from mgtools.translation.xliff import export_xliff2, export_xliff12, import_xliff


class TranslationFormat(StrEnum):
    """A format translation units are exchanged with translation tools in."""

    XLIFF2 = "xliff-2.0"
    XLIFF12 = "xliff-1.2"
    PO = "po"

    @property
    def suffix(self) -> str:
        """The usual extension of the format's files."""
        return _SUFFIXES[self]


_SUFFIXES = {
    TranslationFormat.XLIFF2: ".xlf",
    TranslationFormat.XLIFF12: ".xliff",
    TranslationFormat.PO: ".po",
}


def export_units(
    units: Iterable[Unit],
    fmt: TranslationFormat,
    *,
    original: str,
    source_language: str,
) -> bytes:
    """Return a document of the units untranslated, naming their file and language.

    Args:
        units: The texts to translate.
        fmt: The format of the document.
        original: The name of the file the units come from.
        source_language: The language of the units, as a BCP 47 tag.
    """
    units = checked(units)
    match fmt:
        case TranslationFormat.XLIFF2:
            return export_xliff2(units, original, source_language)
        case TranslationFormat.XLIFF12:
            return export_xliff12(units, original, source_language)
        case TranslationFormat.PO:
            # PO records no source language: its Language header is the translation's.
            return export_po(units, original)


def import_units(data: bytes) -> dict[str, str]:
    """Return the translation of each unit by id, or its source when untranslated.

    Args:
        data: A document in any of the formats.
    """
    return import_xliff(data) if _is_xml(data) else import_po(data)


def find_document(directory: Path, stem: str) -> Path:
    """Return the one translation document named stem in directory, of any format.

    Args:
        directory: The folder to look in.
        stem: The document's name without its suffix.
    """
    names = [stem + fmt.suffix for fmt in TranslationFormat]
    found = [directory / name for name in names if (directory / name).is_file()]
    if len(found) != 1:
        msg = f"{directory} must hold one of {', '.join(names)}, not {len(found)}"
        raise ValueError(msg)
    return found[0]


def read_document(path: Path, ids: Collection[str] = ()) -> dict[str, str]:
    """Return the texts of a document by unit id, which must be ids when given.

    Args:
        path: The document to read.
        ids: The ids the document must hold and no others, or none to take any.
    """
    with located(path):
        texts = import_units(path.read_bytes())
        if missing := [unit_id for unit_id in ids if unit_id not in texts]:
            raise ValueError(_listed("Units are missing", missing))
        if ids and (unknown := sorted(texts.keys() - set(ids))):
            raise ValueError(_listed("Units name no text of the file", unknown))
    return texts


def _listed(problem: str, ids: list[str]) -> str:
    """Return a message naming a problem and the first of the ids it concerns."""
    more = f" and {len(ids) - 1} more" if len(ids) > 1 else ""
    return f"{problem}: {ids[0]}{more}"


def _is_xml(data: bytes) -> bool:
    # XML may come in UTF-16, which gettext does not support.
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return True
    return data.removeprefix(codecs.BOM_UTF8).lstrip().startswith(b"<")
