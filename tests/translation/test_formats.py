import codecs
from pathlib import Path

import pytest
from lxml import etree
from translate.storage.pypo import pofile

from mgtools.errors import FormatError
from mgtools.translation import (
    TranslationFormat,
    Unit,
    export_units,
    find_document,
    import_units,
    read_document,
)
from tests.editing import with_targets

UNITS = [
    Unit("mg1.b00.e000", "Snake, do you read me?{wait}", ("speaker: Big Boss",)),
    Unit("mg1.b00.e001", "First line\nSecond line\n", ("2 lines", "at most\n48 bytes")),
    Unit("mg2.b22.e005", '  "quoted" & <tagged>\t'),
    Unit("res:12", ""),
    Unit("0012ab34.pl", "Zażółć gęślą jaźń \U0001f600\r\n"),
]
XLIFF_NAMESPACES = {
    TranslationFormat.XLIFF2: "{urn:oasis:names:tc:xliff:document:2.0}",
    TranslationFormat.XLIFF12: "{urn:oasis:names:tc:xliff:document:1.2}",
}
EVERY_FORMAT = pytest.mark.parametrize("fmt", list(TranslationFormat))
XLIFF_FORMATS = pytest.mark.parametrize("fmt", list(XLIFF_NAMESPACES))


def export(units: list[Unit], fmt: TranslationFormat) -> bytes:
    return export_units(units, fmt, original="english.raw", source_language="en")


def translate(text: str) -> str:
    return f"PL[{text}]"


def notes_of(data: bytes, fmt: TranslationFormat) -> dict[str, str]:
    """Return the notes of each unit of a document that has some, a line each.

    Args:
        data: The document.
        fmt: The format of the document.
    """
    if fmt is TranslationFormat.PO:
        units = pofile.parsestring(data).units
        found = {u.getcontext(): u.getnotes("developer") for u in units}
    else:
        namespace = XLIFF_NAMESPACES[fmt]
        unit_tag = "unit" if fmt is TranslationFormat.XLIFF2 else "trans-unit"
        found = {
            u.get("id"): "\n".join(n.text or "" for n in u.iter(f"{namespace}note"))
            for u in etree.fromstring(data).iter(f"{namespace}{unit_tag}")
        }
    return {unit_id: text for unit_id, text in found.items() if text}


@EVERY_FORMAT
def test_translations_replace_sources_and_untranslated_units_keep_theirs(
    fmt: TranslationFormat,
) -> None:
    translated = ("mg1.b00.e000", "mg2.b22.e005", "0012ab34.pl")
    targets = {u.id: translate(u.source) if u.id in translated else "" for u in UNITS}

    data = with_targets(export(UNITS, fmt), fmt, targets)

    assert import_units(data) == {
        "mg1.b00.e000": "PL[Snake, do you read me?{wait}]",
        "mg1.b00.e001": "First line\nSecond line\n",
        "mg2.b22.e005": 'PL[  "quoted" & <tagged>\t]',
        "res:12": "",
        "0012ab34.pl": "PL[Zażółć gęślą jaźń \U0001f600\r\n]",
    }


@EVERY_FORMAT
def test_notes_reach_the_translation_tool_and_stay_through_it(
    fmt: TranslationFormat,
) -> None:
    data = with_targets(export(UNITS, fmt), fmt, {u.id: translate(u.source) for u in UNITS})

    assert notes_of(data, fmt) == {
        "mg1.b00.e000": "speaker: Big Boss",
        "mg1.b00.e001": "2 lines\nat most\n48 bytes",
    }


@EVERY_FORMAT
def test_private_use_characters_are_named_in_a_note(fmt: TranslationFormat) -> None:
    unit = Unit("res:1", "Press \ue082 or \ue084, then \ue082.", ("Item",))

    data = export([unit], fmt)

    assert notes_of(data, fmt) == {
        "res:1": "Item\nKeep its private-use characters, which tools may not show: U+E082, U+E084"
    }


@XLIFF_FORMATS
def test_placeholders_stay_plain_text_in_xliff(fmt: TranslationFormat) -> None:
    root = etree.fromstring(export(UNITS[:1], fmt))
    source = next(root.iter(f"{XLIFF_NAMESPACES[fmt]}source"))

    assert source.text == "Snake, do you read me?{wait}"
    assert len(source) == 0


def test_xliff2_units_hold_their_notes_before_one_segment() -> None:
    root = etree.fromstring(export(UNITS[:1], TranslationFormat.XLIFF2))
    unit = next(root.iter(f"{XLIFF_NAMESPACES[TranslationFormat.XLIFF2]}unit"))

    assert [etree.QName(child).localname for child in unit] == ["notes", "segment"]


@pytest.mark.parametrize(
    ("fmt", "language", "original"),
    [
        (TranslationFormat.XLIFF2, "/*/@srcLang", "/*/*[1]/@original"),
        (TranslationFormat.XLIFF12, "/*/*[1]/@source-language", "/*/*[1]/@original"),
    ],
)
def test_xliff_documents_name_the_original_file_and_its_language(
    fmt: TranslationFormat, language: str, original: str
) -> None:
    root = etree.fromstring(export(UNITS, fmt))

    assert root.xpath(language) == ["en"]
    assert root.xpath(original) == ["english.raw"]


def test_po_documents_name_the_original_file() -> None:
    store = pofile.parsestring(export(UNITS, TranslationFormat.PO))

    assert store.parseheader()["Project-Id-Version"] == "english.raw"


def test_fuzzy_po_translations_are_not_used() -> None:
    store = pofile.parsestring(export(UNITS[:1], TranslationFormat.PO))
    store.units[1].target = translate(UNITS[0].source)
    store.units[1].markfuzzy()

    assert import_units(bytes(store)) == {"mg1.b00.e000": UNITS[0].source}


def test_segments_a_tool_split_are_joined_back() -> None:
    data = b"""<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.0">
    <file id="f1"><unit id="a">
    <segment><source>One.</source><target>First.</target></segment>
    <ignorable><source> </source></ignorable>
    <segment><source>Two.</source></segment>
    </unit></file></xliff>"""

    assert import_units(data) == {"a": "First. Two."}


@EVERY_FORMAT
@pytest.mark.parametrize("mark", [b"", codecs.BOM_UTF8])
def test_untranslated_documents_import_as_the_sources(fmt: TranslationFormat, mark: bytes) -> None:
    data = mark + export(UNITS, fmt)

    assert import_units(data) == {u.id: u.source for u in UNITS}


@XLIFF_FORMATS
def test_xliff_in_utf_16_is_read(fmt: TranslationFormat) -> None:
    text = export(UNITS, fmt).decode().replace("UTF-8", "UTF-16", 1)

    assert import_units(text.encode("utf-16")) == {u.id: u.source for u in UNITS}


@EVERY_FORMAT
@pytest.mark.parametrize(
    ("source", "notes", "character"),
    [
        ("a\x0bb", (), "000B"),
        ("text", ("a note\x00",), "0000"),
        (chr(0xD800), (), "D800"),
        (chr(0xFFFF), (), "FFFF"),
    ],
)
def test_characters_documents_cannot_carry_are_refused(
    fmt: TranslationFormat, source: str, notes: tuple[str, ...], character: str
) -> None:
    with pytest.raises(ValueError, match=rf"'id' holds U\+{character}, which"):
        export([Unit("id", source, notes)], fmt)


@EVERY_FORMAT
@pytest.mark.parametrize("unit_id", ["", "two words", "100%"])
def test_ids_that_are_not_xml_names_are_refused(fmt: TranslationFormat, unit_id: str) -> None:
    with pytest.raises(ValueError, match="is not letters, digits"):
        export([Unit(unit_id, "text")], fmt)


@EVERY_FORMAT
def test_repeated_ids_are_refused(fmt: TranslationFormat) -> None:
    with pytest.raises(ValueError, match="Two units have the id 'a'"):
        export([Unit("a", "one"), Unit("a", "two")], fmt)


@EVERY_FORMAT
def test_documents_repeating_an_id_are_refused(fmt: TranslationFormat) -> None:
    data = export([Unit("a", "one"), Unit("b", "two")], fmt).replace(b'"b"', b'"a"')

    with pytest.raises(FormatError, match="two units with the id 'a'"):
        import_units(data)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (b'msgid "x"\nmsgstr ""\n', "has no context"),
        (
            b'<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.0">'
            b'<file id="f"><unit><segment><source>x</source></segment></unit>'
            b"</file></xliff>",
            "A unit on line 1 has no id",
        ),
        (
            b'<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">'
            b'<file original="f"><body><trans-unit><source>x</source></trans-unit>'
            b"</body></file></xliff>",
            "A unit on line 1 has no id",
        ),
    ],
)
def test_units_without_an_id_are_refused(document: bytes, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        import_units(document)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (b"<tmx version='1.4'/>", "Not an XLIFF 2.0 or 1.2 document: .* tmx"),
        (
            b"<xliff xmlns='urn:oasis:names:tc:xliff:document:1.1' version='1.1'/>",
            "Not an XLIFF 2.0 or 1.2 document",
        ),
        (b"<!-- unclosed", "Cannot read the XML document"),
        (b'msgid "unclosed', "Cannot read the PO document"),
    ],
)
def test_unreadable_documents_are_reported(document: bytes, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        import_units(document)


def test_po_refuses_sources_it_would_read_as_comments() -> None:
    with pytest.raises(ValueError, match="'a' starts with _:"):
        export([Unit("a", "_: not a comment")], TranslationFormat.PO)


@pytest.mark.parametrize(("msgstr", "imported"), [("Przytrzymaj", "Przytrzymaj"), ("", None)])
def test_po_lines_rewrapped_into_comments_only_matter_untranslated(
    msgstr: str, imported: str | None
) -> None:
    data = f'msgctxt "a"\nmsgid ""\n"Hold to save "\n"_:1 slot"\nmsgstr "{msgstr}"\n'

    if imported is None:
        with pytest.raises(FormatError, match="a: a line starting with _:"):
            import_units(data.encode())
    else:
        assert import_units(data.encode()) == {"a": imported}


def test_a_folder_holds_one_document_of_a_name_in_any_format(tmp_path: Path) -> None:
    (tmp_path / "text.po").touch()
    (tmp_path / "glyphs.xlf").touch()

    assert find_document(tmp_path, "text") == tmp_path / "text.po"
    (tmp_path / "text.xlf").touch()
    with pytest.raises(ValueError, match=r"one of text\.xlf, text\.xliff, text\.po, not 2"):
        find_document(tmp_path, "text")
    with pytest.raises(ValueError, match="not 0"):
        find_document(tmp_path, "texts")


@pytest.mark.parametrize(
    ("ids", "message"),
    [
        (["a", "c", "d"], "Units are missing: c and 1 more"),
        (["a"], "Units name no text of the file: b$"),
    ],
)
def test_documents_must_hold_the_units_asked_for(
    tmp_path: Path, ids: list[str], message: str
) -> None:
    path = tmp_path / "text.po"
    path.write_bytes(export([Unit("a", "one"), Unit("b", "two")], TranslationFormat.PO))

    assert read_document(path, ["b", "a"]) == {"a": "one", "b": "two"}
    with pytest.raises(ValueError, match=rf"text\.po: {message}"):
        read_document(path, ids)
