from pathlib import Path

import pytest

from mgtools.errors import FormatError
from mgtools.mc.stov import (
    StovString,
    _crypt,
    decode_stov,
    encode_stov,
    export_stov,
    import_stov,
)
from mgtools.translation import TranslationFormat, Unit, export_units

STRINGS = [
    StovString(0x10, "all", "\ue082 OK"),
    StovString(0x2A, "en", "Two\r\nlines"),
    StovString(0x30, "sp", ""),
]
PLAIN = (
    bytes.fromhex("4800000000000000")
    + bytes.fromhex("10000000 00000000 0000000000000000 0700000000000000")
    + bytes.fromhex("2a000000 02000000 0700000000000000 1200000000000000")
    + bytes.fromhex("30000000 06000000 1200000000000000 1300000000000000")
    + "\ue082 OK\0".encode()
    + b"Two\r\nlines\0"
    + b"\0"
)


@pytest.mark.parametrize(
    ("name", "keystream"),
    [("stovk", "6fa22252595ae266"), ("stovc", "7aeb47f6d1425f31")],
)
def test_the_keystream_is_seeded_from_the_file_name_up_to_its_first_dot(
    name: str, keystream: str
) -> None:
    for path in (f"{name}.bin", f"EngineSupport/{name}.pl.bin"):
        assert encode_stov([], path) == bytes.fromhex(keystream)


def test_strings_follow_their_table_encrypted_for_a_name_the_game_reads() -> None:
    data = encode_stov(STRINGS, "stovc.bin")

    assert _crypt(data, "stovc.bin") == PLAIN
    assert decode_stov(data, "stovc.bin") == STRINGS
    with pytest.raises(FormatError, match=r"Cannot decrypt stovk\.bin: a string table"):
        decode_stov(data, "EngineSupport/stovk.bin")
    with pytest.raises(ValueError, match="a table named stovc_pl would be unreadable"):
        encode_stov(STRINGS, "stovc_pl.bin")


def test_strings_are_sorted_by_their_unique_ids() -> None:
    assert encode_stov(reversed(STRINGS), "stovc.bin") == encode_stov(STRINGS, "stovc.bin")
    with pytest.raises(ValueError, match="Two strings have the id 00000010"):
        encode_stov([*STRINGS, StovString(0x10, "jp", "")], "stovc.bin")


@pytest.mark.parametrize(
    ("offset", "byte", "message"),
    [
        (0, 0x47, "takes 71 bytes, not a multiple of 24"),
        (0x40, 0x11, "00000030 is not stored right after"),
        (len(PLAIN) - 1, ord("!"), "00000030 does not end with its only NUL"),
        (0x3C, 0x07, "00000030 has the unknown language 7"),
        (0x38, 0x20, "00000020 follows 0000002a out of id order"),
        (len(PLAIN), 0x00, "1 bytes follow the last string"),
        (len(PLAIN) - 12, 0xFF, "0000002a is not UTF-8"),
    ],
)
def test_malformed_tables_are_reported(offset: int, byte: int, message: str) -> None:
    plain = PLAIN[:offset] + bytes([byte]) + PLAIN[offset + 1 :]

    with pytest.raises(FormatError, match=message):
        decode_stov(_crypt(plain, "stovk.bin"), "stovk.bin")


def test_translations_replace_the_text_with_crlf_line_breaks(tmp_path: Path) -> None:
    path = tmp_path / "stovc.po"
    export_stov(STRINGS, path, TranslationFormat.PO, "stovc.bin")
    untranslated = 'msgid "Two\\nlines"\nmsgstr ""'
    translated = 'msgid "Two\\nlines"\nmsgstr "Dwie\\nlinie"'
    path.write_text(path.read_text("utf-8").replace(untranslated, translated), "utf-8")

    assert import_stov(path) == [
        STRINGS[0],
        StovString(0x2A, "en", "Dwie\r\nlinie"),
        STRINGS[2],
    ]


@pytest.mark.parametrize("unit_id", ["2a.en", "0000002a", "0000002a.pl", "0000002A.en"])
def test_unit_ids_that_name_no_string_are_refused(tmp_path: Path, unit_id: str) -> None:
    path = tmp_path / "stovc.xlf"
    document = export_units(
        [Unit(unit_id, "text")],
        TranslationFormat.XLIFF2,
        original="stovc.bin",
        source_language="en",
    )
    path.write_bytes(document)

    with pytest.raises(ValueError, match=f"'{unit_id}' is not a unit id"):
        import_stov(path)
