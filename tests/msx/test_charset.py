import re

import pytest

from mgtools.msx.charset import EU_CHARMAP, JP_CHARMAP, Charset
from mgtools.msx.game import Game

MG1 = Charset(Game.MG1, EU_CHARMAP)
MG2 = Charset(Game.MG2, EU_CHARMAP)


@pytest.mark.parametrize(
    ("charset", "data", "text"),
    [
        (MG1, b"Snake!\nOver.", "Snake!\nOver."),
        (MG1, b"S\xbdLECTION \xbdQUIPEMENT \xdf", "SÉLECTION ÉQUIPEMENT °"),
        (MG1, b"C:\\GAME", "C:\\GAME"),
        (MG1, b"Push |0 or |1.", "Push {btn:0} or {btn:1}."),
        (MG1, b"\x83X\x83l\x81[\x83N", "スネーク"),
        (
            MG2,
            b"Campbell\\r: \n\\1Hi.\\B14\\S-1\\w",
            "Campbell{r}: \n{speed:1}Hi.{bgm:14}{se:-1}{wait}",
        ),
        (MG2, b"\\s\\e\\f\\W|7", "{s}{e}{f}{autowait}{btn:7}"),
        (Charset(Game.MG2, JP_CHARMAP), b"sv\xb6j", "svůj"),
    ],
)
def test_texts_read_with_characters_and_placeholders_and_write_back(
    charset: Charset, data: bytes, text: str
) -> None:
    assert charset.decode(data) == text
    assert charset.encode(text) == data


@pytest.mark.parametrize(
    ("charset", "data", "text"),
    [
        (MG1, b"{}\x7f\xa0\x80\xfd", "{x:7B}{x:7D}{x:7F}{x:A0}{x:80}{x:FD}"),
        (MG2, b"\\x\\", "{x:5C}x{x:5C}"),
        (MG2, b"\\B{1", "{x:5C}B{x:7B}1"),
        (MG1, b"\x81", "{x:81}"),
        (MG1, b"\x81\x8b", "{sjis:818B}"),
        (MG1, b"\x87\x90", "{sjis:8790}"),
    ],
)
def test_bytes_that_are_no_character_read_as_their_codes_and_write_back_in_either_case(
    charset: Charset, data: bytes, text: str
) -> None:
    lowercase = re.sub(r":[0-9A-F]+}", lambda code: code[0].lower(), text)

    assert charset.decode(data) == text
    assert charset.encode(text) == charset.encode(lowercase) == data


@pytest.mark.parametrize("game", list(Game))
def test_any_bytes_survive_reading_and_writing(game: Game) -> None:
    charset = Charset(game, EU_CHARMAP)
    data = bytes(range(256)) + b"\\B1\\S\\9|\\|x\x81\x40\xe0"

    assert charset.encode(charset.decode(data)) == data


def test_characters_tell_the_bytes_they_come_from() -> None:
    pieces = list(MG2.characters(b"A\\w\x81\x45|2\xb9"))

    assert pieces == [
        (b"A", "A"),
        (b"\\w", "{wait}"),
        (b"\x81\x45", "・"),
        (b"|2", "{btn:2}"),
        (b"\xb9", "é"),
    ]


@pytest.mark.parametrize(
    ("charset", "text", "message"),
    [
        (MG1, "{wait}", "{wait} is not a placeholder of MG1"),
        (MG1, "{bgm:14}", "{bgm:14} is not a placeholder of MG1"),
        (MG2, "{bgm:1}", "{bgm:1} is not a placeholder of MG2"),
        (MG2, "{speed:0}", "{speed:0} is not"),
        (MG2, "{btn:x}", "{btn:x} is not"),
        (MG2, "{btn:²}", "{btn:²} is not"),
        (MG2, "{x:5}", "{x:5} is not"),
        (MG2, "{sjis:81}", "{sjis:81} is not"),
        (MG2, "{wait", "The { of '{wait' opens no placeholder"),
        (MG2, "{Wait}", "The { of '{Wait}' opens no placeholder"),
        (MG2, "a } b", "A } closes no placeholder"),
        (MG2, "C:\\GAME", "A backslash starts an engine code in MG2"),
        (MG1, "Zażółć", r"'ż' \(U\+017C\) has no code: name it in the charmap"),
        (MG1, "tab\there", r"'\\t' \(U\+0009\) has no code"),
        (MG1, "ｱ", r"'ｱ' \(U\+FF71\) has no code"),
    ],
)
def test_texts_the_game_cannot_store_are_refused(charset: Charset, text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        charset.encode(text)


def test_a_charmap_can_name_new_letters_for_the_free_codes() -> None:
    polish = Charset(Game.MG1, {0xA0: "ą", 0xB3: "Ł", 0xC9: "ó", 0x7F: "ż"})

    assert polish.encode("Łóżką") == b"\xb3\xc9\x7fk\xa0"
    assert polish.decode(b"\xb3\xc9\x7fk\xa0\xb9") == "Łóżką{x:B9}"


@pytest.mark.parametrize(
    ("charmap", "message"),
    [
        ({0x41: "ą"}, "names 41, but only 7F and A0 to DF are free"),
        ({0xE0: "ą"}, "names E0, but only"),
        ({0xA0: "a"}, "gives A0 'a', not a new character"),
        ({0xA0: "\t"}, r"gives A0 '\\t', not a new character"),
        ({0xA0: "ąę"}, "gives A0 'ąę', not a new character"),
        ({0xA0: "ą", 0xA1: "ą"}, "gives 'ą' to two codes"),
    ],
)
def test_charmaps_give_each_free_code_one_new_character(
    charmap: dict[int, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        Charset(Game.MG1, charmap)
