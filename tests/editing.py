"""Edits of exported files made the way people and their tools make them."""

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from lxml import etree
from translate.storage.pypo import pofile

from mgtools.fileio import read_json
from mgtools.translation import TranslationFormat


def edit_json(path: Path, edit: Callable[[Any], object]) -> None:
    """Change an exported JSON file in place.

    Args:
        path: The JSON file to change.
        edit: Changes the value read from the file, which is then written back.
    """
    document = read_json(path)
    edit(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def with_targets(data: bytes, fmt: TranslationFormat, targets: Mapping[str, str]) -> bytes:
    """Return a translation document with targets filled in the way a translation tool does.

    Args:
        data: The document as exported.
        fmt: The format of the document.
        targets: The target of each unit to fill in by unit id; other units stay untranslated.
    """
    if fmt is TranslationFormat.PO:
        store = pofile.parsestring(data)
        for unit in store.units:
            if (text := targets.get(unit.getcontext())) is not None:
                unit.target = text
        return bytes(store)
    root = etree.fromstring(data)
    namespace = root.nsmap[None]
    tag = "unit" if fmt is TranslationFormat.XLIFF2 else "trans-unit"
    for unit in root.iter(f"{{{namespace}}}{tag}"):
        if (text := targets.get(unit.attrib["id"])) is not None:
            target = etree.Element(f"{{{namespace}}}target")
            target.text = text
            next(unit.iter(f"{{{namespace}}}source")).addnext(target)
    return bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
