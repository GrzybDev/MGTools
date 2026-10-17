"""Exchanging translation units through XLIFF 2.0 and 1.2.

Each unit becomes a unit with one segment (XLIFF 2.0) or a trans-unit (XLIFF
1.2) that preserves whitespace, with its notes in note elements. Placeholders
such as {wait} stay plain text, never inline codes: OmegaT renumbers the third
and later inline codes of a segment wrongly. A unit takes its target when that
is not empty, whatever its state, since OmegaT marks no state in XLIFF 2.0; the
segments of a unit that a tool split are joined back.
"""

from collections.abc import Callable, Iterable, Iterator

from lxml import etree

from mgtools.errors import FormatError
from mgtools.translation.unit import Unit, collected

type _Tag = Callable[[str], str]

_XLIFF2 = "urn:oasis:names:tc:xliff:document:2.0"
_XLIFF12 = "urn:oasis:names:tc:xliff:document:1.2"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _xliff2(name: str) -> str:
    """Return the qualified name of an XLIFF 2.0 element."""
    return f"{{{_XLIFF2}}}{name}"


def _xliff12(name: str) -> str:
    """Return the qualified name of an XLIFF 1.2 element."""
    return f"{{{_XLIFF12}}}{name}"


def export_xliff2(units: Iterable[Unit], original: str, source_language: str) -> bytes:
    """Return an XLIFF 2.0 document with the units untranslated.

    Args:
        units: The texts to translate.
        original: The name of the file the units come from.
        source_language: The language of the units, as a BCP 47 tag.
    """
    root = etree.Element(
        _xliff2("xliff"), nsmap={None: _XLIFF2}, version="2.0", srcLang=source_language
    )
    file = etree.SubElement(root, _xliff2("file"), id="f1", original=original)
    for unit in units:
        element = etree.SubElement(file, _xliff2("unit"), id=unit.id)
        element.set(_XML_SPACE, "preserve")
        if unit.notes:
            notes = etree.SubElement(element, _xliff2("notes"))
            for note in unit.notes:
                etree.SubElement(notes, _xliff2("note")).text = note
        segment = etree.SubElement(element, _xliff2("segment"))
        etree.SubElement(segment, _xliff2("source")).text = unit.source
    return _serialized(root)


def export_xliff12(units: Iterable[Unit], original: str, source_language: str) -> bytes:
    """Return an XLIFF 1.2 document with the units untranslated.

    Args:
        units: The texts to translate.
        original: The name of the file the units come from.
        source_language: The language of the units, as a BCP 47 tag.
    """
    root = etree.Element(_xliff12("xliff"), nsmap={None: _XLIFF12}, version="1.2")
    file = etree.SubElement(root, _xliff12("file"), original=original)
    file.set("source-language", source_language)
    file.set("datatype", "plaintext")
    body = etree.SubElement(file, _xliff12("body"))
    for unit in units:
        element = etree.SubElement(body, _xliff12("trans-unit"), id=unit.id)
        element.set(_XML_SPACE, "preserve")
        etree.SubElement(element, _xliff12("source")).text = unit.source
        for note in unit.notes:
            etree.SubElement(element, _xliff12("note")).text = note
    return _serialized(root)


def import_xliff(data: bytes) -> dict[str, str]:
    """Return the text of each unit of an XLIFF 2.0 or 1.2 document by id.

    Args:
        data: The XLIFF document.
    """
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as error:
        msg = f"Cannot read the XML document: {error}"
        raise FormatError(msg) from error
    if root.tag == _xliff2("xliff"):
        return collected(_xliff2_texts(root))
    if root.tag == _xliff12("xliff"):
        return collected(_xliff12_texts(root))
    msg = f"Not an XLIFF 2.0 or 1.2 document: its root element is {etree.QName(root).text}"
    raise FormatError(msg)


def _xliff2_texts(root: etree._Element) -> Iterator[tuple[str, str]]:
    """Yield the id and text of each unit of an XLIFF 2.0 document, segments joined."""
    parts = {_xliff2("segment"), _xliff2("ignorable")}
    for unit in root.iter(_xliff2("unit")):
        texts = (_text(part, _xliff2) for part in unit if part.tag in parts)
        yield _id(unit), "".join(texts)


def _xliff12_texts(root: etree._Element) -> Iterator[tuple[str, str]]:
    """Yield the id and text of each trans-unit of an XLIFF 1.2 document."""
    for unit in root.iter(_xliff12("trans-unit")):
        yield _id(unit), _text(unit, _xliff12)


def _id(unit: etree._Element) -> str:
    """Return the id of a unit element, refusing one without."""
    if (unit_id := unit.get("id")) is None:
        msg = f"A unit on line {unit.sourceline} has no id"
        raise FormatError(msg)
    return str(unit_id)


def _text(element: etree._Element, tag: _Tag) -> str:
    """Return the text of an element's target, or of its source when untranslated."""
    for name in ("target", "source"):
        child = element.find(tag(name))
        if child is not None and (text := str(child.xpath("string()"))):
            return text
    return ""


def _serialized(root: etree._Element) -> bytes:
    """Return a document as indented UTF-8 XML with its declaration."""
    return bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True))
