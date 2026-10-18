"""The editable form of a GCX script: a folder of its listing, texts and glyphs.

The listing holds the code and the resources, a translation document the UTF-8
texts of a Bluepoint file, and a PNG the glyphs.
"""

from dataclasses import replace
from itertools import batched
from pathlib import Path

from mgtools.bitmap import glyph_sheet, read_glyph_sheet
from mgtools.errors import located
from mgtools.fileio import write_atomically, write_png
from mgtools.mc.gcx.legacy import decode_legacy
from mgtools.mc.gcx.listing import format_listing
from mgtools.mc.gcx.parser import parse_listing
from mgtools.mc.gcx.script import (
    GLYPH_BYTES,
    GLYPH_SIZE,
    Resource,
    Script,
    StringResource,
)
from mgtools.translation import (
    TranslationFormat,
    Unit,
    export_units,
    find_document,
    read_document,
)

LISTING = "script.gcl"
GLYPHS = "glyphs.png"
_TEXTS = "text"
_COLUMNS = 16


def export_script(
    script: Script,
    directory: Path,
    fmt: TranslationFormat,
    *,
    original: str,
    source_language: str,
) -> None:
    """Write the editable form of a script, naming its file and texts' language.

    Args:
        script: The script to write.
        directory: The folder to write the listing, texts and glyphs to.
        fmt: The format of the translation document of the texts.
        original: The name of the script's file, which the document records.
        source_language: The language of the texts, which the document records.
    """
    write_atomically(directory / LISTING, format_listing(script).encode())
    units = [
        Unit(f"res:{index}", resource.text, _notes(resource))
        for index, resource in enumerate(script.resources)
        if isinstance(resource, StringResource) and resource.text is not None
    ]
    if units:
        document = export_units(units, fmt, original=original, source_language=source_language)
        write_atomically(directory / f"{_TEXTS}{fmt.suffix}", document)
    if script.glyphs:
        glyphs = list(map(bytes, batched(script.glyphs, GLYPH_BYTES, strict=True)))
        # An image of fewer glyphs than a row is only as wide as they are.
        sheet = glyph_sheet(glyphs, GLYPH_SIZE, min(len(glyphs), _COLUMNS))
        write_png(directory / GLYPHS, sheet)


def import_script(directory: Path) -> Script:
    """Read the editable form of a script.

    Args:
        directory: The folder export_script wrote.
    """
    path = directory / LISTING
    with located(path):
        script = parse_listing(path.read_text(encoding="utf-8-sig"))
    if script.glyphs:
        count = len(script.glyphs) // GLYPH_BYTES
        glyphs = read_glyph_sheet(directory / GLYPHS, count, GLYPH_SIZE, min(count, _COLUMNS))
        script = replace(script, glyphs=b"".join(glyphs))
    if script.bluepoint:
        script = replace(script, resources=_with_texts(script.resources, directory))
    return script


def _notes(resource: StringResource) -> tuple[str, ...]:
    """Return a note with the PS2 text of a string when it differs from the UTF-8 one."""
    legacy = decode_legacy(resource.legacy)
    return () if legacy == resource.text else (f"PS2 text: {legacy}",)


def _with_texts(resources: tuple[Resource, ...], directory: Path) -> tuple[Resource, ...]:
    """Return the resources with the UTF-8 texts of the translation document in directory."""
    ids = [
        f"res:{index}"
        for index, resource in enumerate(resources)
        if isinstance(resource, StringResource)
    ]
    if not ids:
        return resources
    texts = read_document(find_document(directory, _TEXTS), ids)
    return tuple(
        replace(resource, text=texts[f"res:{index}"])
        if isinstance(resource, StringResource)
        else resource
        for index, resource in enumerate(resources)
    )
