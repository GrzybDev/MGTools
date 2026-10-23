from pathlib import Path

import pytest

from mgtools.mc.gcx.dictionary import read_dictionary
from mgtools.mc.gcx.listing import format_listing
from mgtools.mc.gcx.nodes import Binary, Block, Command, Expression, Int, Operator, StrCode
from mgtools.mc.gcx.parser import parse_listing
from mgtools.mc.gcx.script import Script
from mgtools.mc.gcx.strcode import strcode

LAMP = strcode("lamp")
OPEN_DOOR = strcode("open_door")
IF = strcode("if")
SCRIPT = Script(
    False,
    1,
    2,
    (),
    Block(
        (
            Command(
                IF,
                (
                    Expression(Binary(Operator.EQUAL, StrCode(LAMP), Int(1))),
                    Block((Command(OPEN_DOOR, (StrCode(0xABCDEF),)),)),
                ),
            ),
        )
    ),
    (),
    b"",
)
NOT_A_NAME = "is not a name: ASCII letters, digits and _, not starting with a digit"


def test_a_dictionary_names_strcodes_in_a_listing_that_compiles_back(tmp_path: Path) -> None:
    path = tmp_path / "names.txt"
    # "jF" hashes like the built-in "if", which it replaces; a repeated line is no conflict,
    # and the words after a name are no part of it.
    text = "379210 lamp // a light\n\n0x966474\topen_door\r\n#000D86 jF\n000D86 jF\n"
    path.write_bytes(text.encode("utf-8-sig"))

    dictionary = read_dictionary(path)
    listing = format_listing(SCRIPT, dictionary.names)

    assert dictionary.names == {LAMP: "lamp", OPEN_DOOR: "open_door", IF: "jF"}
    assert dictionary.skipped == {}
    assert "main {\n    jF (lamp == 1) {\n        open_door #ABCDEF;\n    };\n}" in listing
    assert parse_listing(listing) == SCRIPT


def test_lines_that_would_not_compile_back_are_skipped_with_their_reason(tmp_path: Path) -> None:
    path = tmp_path / "names.txt"
    lines = (
        "strcode name",
        "379210",
        "37921G lamp",
        "379210 9lamp",
        "379210 ランプ",
        "379210 lamq",
        "000D86 if",
        "000D86 jF",
        "966474 open_door",
    )
    path.write_bytes("\n".join(lines).encode("euc_jp"))

    dictionary = read_dictionary(path)

    assert dictionary.names == {IF: "if", OPEN_DOOR: "open_door"}
    assert dictionary.skipped == {
        1: "'strcode' is not a strcode of up to six hex digits",
        2: "expected a strcode in hex and a name, found '379210'",
        3: "'37921G' is not a strcode of up to six hex digits",
        4: f"'9lamp' {NOT_A_NAME}",
        5: f"'ランプ' {NOT_A_NAME}",
        6: "lamq hashes to #379211, not #379210",
        8: "#000D86 already has the name if",
    }


def test_a_file_neither_utf8_nor_euc_jp_is_refused_with_its_name(tmp_path: Path) -> None:
    path = tmp_path / "names.txt"
    path.write_bytes(b"379210 lamp\x80")

    with pytest.raises(ValueError, match=r"names\.txt: not UTF-8 or EUC-JP text"):
        read_dictionary(path)
