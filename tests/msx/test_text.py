from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from lxml import etree
from PIL import Image
from translate.storage.pypo import pofile

from mgtools.bitmap import grey_image, pack_2bpp
from mgtools.errors import FormatError
from mgtools.fileio import read_json
from mgtools.msx.charset import PLACEHOLDERS
from mgtools.msx.font import DoubleByteGlyph, Font, Glyph, decode_font, encode_font
from mgtools.msx.game import Game
from mgtools.msx.text import export_text_and_font, import_text_and_font
from mgtools.translation import TranslationFormat, import_units
from tests.editing import edit_json, with_targets
from tests.msx.samples import MG1_BLOCKS, MG2_BLOCKS, strings, text_font

BLOCKS = {Game.MG1: MG1_BLOCKS, Game.MG2: MG2_BLOCKS}
FONT = text_font()
PAGES = encode_font(FONT)


def export(
    game: Game,
    directory: Path,
    fmt: TranslationFormat = TranslationFormat.PO,
    font: Font = FONT,
) -> None:
    export_text_and_font(game, BLOCKS[game], encode_font(font), directory, fmt)


def translate(directory: Path, translations: dict[str, str]) -> None:
    path = directory / "text.po"
    path.write_bytes(with_targets(path.read_bytes(), TranslationFormat.PO, translations))


def notes(directory: Path) -> dict[str, str]:
    store = pofile.parsestring((directory / "text.po").read_bytes())
    return {unit.getcontext(): unit.getnotes("developer") for unit in store.units}


@pytest.mark.parametrize("fmt", list(TranslationFormat))
@pytest.mark.parametrize("game", list(Game))
def test_untranslated_exports_import_back_unchanged(
    game: Game, fmt: TranslationFormat, tmp_path: Path
) -> None:
    export(game, tmp_path, fmt)

    assert import_text_and_font(game, tmp_path) == (BLOCKS[game], PAGES)


def test_mg1_keeps_its_tables_warp_points_and_styles_beside_the_strings(
    tmp_path: Path,
) -> None:
    export(Game.MG1, tmp_path)

    layout = read_json(tmp_path / "text.json")
    assert (tmp_path / "text/b10.bin").read_bytes() == MG1_BLOCKS[10]
    assert sorted(path.name for path in (tmp_path / "text").iterdir()) == [
        f"b{block:02d}.bin" for block in (0, 1, 2, 10, 11, 16)
    ]
    assert layout["warps"][1] == {
        "params": "00000007",
        "name": "倉庫の入口",
        "x": 2048,
        "y": 96,
        "flag": 0,
    }
    assert layout["styles"]["b04"] == [2, 26]
    assert list(layout["styles"]) == [f"b{b:02d}" for b in (3, 4, 5, 6, 7, 8, 9, 13, 14, 15)]


def test_units_are_named_by_block_and_position_and_read_as_text(
    tmp_path: Path,
) -> None:
    export(Game.MG2, tmp_path)

    texts = import_units((tmp_path / "text.po").read_bytes())

    assert len(texts) == 25
    assert texts["mg2.b03.e000"] == "Campbell{r}: \n{speed:2}Snake!{bgm:14}{wait}"
    assert texts["mg2.b19.e000"] == "Push the {btn:4} button."
    assert texts["mg2.b22.e001"] == "★★★"


def test_a_charmap_given_on_export_names_the_characters_of_its_codes(
    tmp_path: Path,
) -> None:
    export_text_and_font(Game.MG1, MG1_BLOCKS, PAGES, tmp_path, TranslationFormat.PO, {0xBD: "Ś"})

    texts = import_units((tmp_path / "text.po").read_bytes())
    assert texts["mg1.b15.e004"] == "CAFŚ"
    assert import_text_and_font(Game.MG1, tmp_path) == (MG1_BLOCKS, PAGES)


def test_notes_give_each_string_its_size_line_limits_and_placeholders(
    tmp_path: Path,
) -> None:
    export(Game.MG1, tmp_path / "mg1")
    export(Game.MG2, tmp_path / "mg2")

    found = notes(tmp_path / "mg1") | notes(tmp_path / "mg2")

    facts = {
        "mg1.b03.e001": ("Style 1 ", "11 bytes", "Wrapped at spaces, at most 48 bytes a line"),
        "mg1.b15.e001": ("8 pixels wide",),
        "mg1.b15.e002": ("Wrapped at spaces, at most 48 bytes a line",),
        "mg1.b15.e003": ("8x8 HUD font",),
        "mg2.b03.e000": ("27 bytes", "at most 45 bytes a line", "at most 10 lines a page"),
        "mg2.b17.e000": ("85 bytes", "at most 45 bytes a line"),
        "mg2.b22.e001": ("72 pixels wide",),
    }
    for unit_id, parts in facts.items():
        assert all(part in found[unit_id] for part in parts), unit_id
    assert "lines a page" not in found["mg2.b17.e000"]
    used = [note for note in found["mg2.b03.e000"].splitlines() if note in PLACEHOLDERS.values()]
    assert used == [PLACEHOLDERS[name] for name in ("wait", "r", "speed", "bgm")]
    assert not set(found["mg2.b17.e000"].splitlines()) & set(PLACEHOLDERS.values())


def test_japanese_fonts_mark_the_texts_japanese_and_unwrapped(tmp_path: Path) -> None:
    japanese = text_font(japanese=True)
    export(Game.MG1, tmp_path / "mg1", font=japanese)
    export(Game.MG2, tmp_path / "mg2", font=japanese)
    export(Game.MG2, tmp_path / "mg2", TranslationFormat.XLIFF2, font=japanese)

    found = notes(tmp_path / "mg1") | notes(tmp_path / "mg2")
    root = etree.fromstring((tmp_path / "mg2/text.xlf").read_bytes())

    assert root.get("srcLang") == "ja"
    assert "Not wrapped, at most 48 bytes a line" in found["mg1.b03.e000"]
    assert "8 pixels wide" in found["mg1.b15.e003"]
    assert "Not wrapped, at most 47 bytes a line" in found["mg2.b03.e000"]
    assert "{wait} hides the byte after it" in found["mg2.b03.e000"]


def test_glyph_0_of_page_4_is_named_after_the_character_the_text_draws_with_it(
    tmp_path: Path,
) -> None:
    export(Game.MG1, tmp_path)

    font = read_json(tmp_path / "font.json")
    assert font["double_byte"] == ["\N{HORIZONTAL ELLIPSIS}", "★"]


def test_translations_replace_the_strings_they_translate(tmp_path: Path) -> None:
    export(Game.MG2, tmp_path)
    translate(
        tmp_path,
        {
            "mg2.b01.e000": "Pistolet",
            "mg2.b03.e001": "Campbell{r}: \nKoniec.{autowait}",
        },
    )

    blocks, pages = import_text_and_font(Game.MG2, tmp_path)

    assert blocks[1] == strings([b"Pistolet"])
    assert blocks[3] == strings([b"Campbell\\r: \n\\2Snake!\\B14\\w", b"Campbell\\r: \nKoniec.\\W"])
    assert blocks[4:] == MG2_BLOCKS[4:]
    assert pages == PAGES


def test_letters_added_to_the_font_can_be_used_by_translations(tmp_path: Path) -> None:
    export(Game.MG1, tmp_path)
    edit_json(tmp_path / "font.json", lambda d: d["charmap"].update(A0="ą"))
    edit_json(tmp_path / "font.json", lambda d: d["pages"][0]["widths"].update(A0=3))
    with Image.open(tmp_path / "font/page0.png") as image:
        image.paste(3, (0, 8 * 24, 3, 9 * 24))
        image.save(tmp_path / "font/page0.png")
    translate(tmp_path, {"mg1.b03.e000": "Ząb"})

    blocks, pages = import_text_and_font(Game.MG1, tmp_path)

    assert blocks[3] == strings([(0, b"Z\xa0b"), (1, b"Phew, safe!")])
    assert decode_font(pages).pages[0].glyphs[0xA0] == Glyph(3, pack_2bpp(b"\3" * 72))


def test_characters_added_to_page_4_can_be_used_by_translations(
    tmp_path: Path,
) -> None:
    export(Game.MG1, tmp_path)
    edit_json(tmp_path / "font.json", lambda d: d["double_byte"].append("「"))
    with Image.open(tmp_path / "font/page4.png") as image:
        image.paste(3, (2 * 24, 0, 3 * 24, 24))
        image.save(tmp_path / "font/page4.png")
    translate(tmp_path, {"mg1.b03.e000": "「Hi"})

    blocks, pages = import_text_and_font(Game.MG1, tmp_path)

    assert blocks[3] == strings([(0, b"\x81\x75Hi"), (1, b"Phew, safe!")])
    assert decode_font(pages).double_byte[2].code == 0x8175


def test_glyphs_added_as_images_of_their_own_can_be_used_by_translations(
    tmp_path: Path,
) -> None:
    export_text_and_font(
        Game.MG1, MG1_BLOCKS, PAGES, tmp_path, TranslationFormat.PO, separate_glyphs=True
    )

    def add_glyphs(document: dict[str, Any]) -> None:
        document["charmap"]["A0"] = "ą"
        document["pages"][0]["widths"]["A0"] = 3
        document["pages"][0]["images"]["A0"] = "a-ogonek.png"
        document["double_byte"].append("「")
        document["double_byte_images"].append("corner-bracket.png")

    edit_json(tmp_path / "font.json", add_glyphs)
    grey_image(b"\3" * 72, (3, 24)).save(tmp_path / "font/page0/a-ogonek.png")
    grey_image(b"\2" * 576, (24, 24)).save(tmp_path / "font/page4/corner-bracket.png")
    translate(tmp_path, {"mg1.b03.e000": "「Ząb"})

    blocks, pages = import_text_and_font(Game.MG1, tmp_path)

    font = decode_font(pages)
    assert blocks[3] == strings([(0, b"\x81\x75Z\xa0b"), (1, b"Phew, safe!")])
    assert font.pages[0].glyphs[0xA0] == Glyph(3, pack_2bpp(b"\3" * 72))
    assert font.double_byte[2] == DoubleByteGlyph(0x8175, pack_2bpp(b"\2" * 576))


@pytest.mark.parametrize(
    ("unit_id", "text", "message"),
    [
        ("mg1.b03.e000", "Zażółć", r"mg1\.b03\.e000: 'ż' \(U\+017C\) has no code"),
        ("mg1.b03.e000", "{wait}", r"mg1\.b03\.e000: {wait} is not a placeholder"),
        (
            "mg1.b03.e000",
            "Ï",
            r"mg1\.b03\.e000: 'Ï' \(C7\) has no glyph on font page 0: give it a "
            r"width on page 0 of font\.json and draw its glyph",
        ),
        (
            "mg1.b03.e000",
            "「",
            r"mg1\.b03\.e000: '「' has no glyph on font page 4: list it in the "
            r"double_byte of font\.json and draw its glyph",
        ),
        (
            "mg1.b15.e003",
            "čFUEL",
            r"'č' is not in the HUD font, which has capitals, digits and B0-DF "
            r"\(images/62\.000\.png\)",
        ),
        ("mg1.b15.e003", "FUEL★", "'★' is not in the HUD font"),
        ("mg1.b15.e003", "Fuel", "'u' is not in the HUD font"),
        ("mg1.b03.e000", "x" * 49, "a word takes 49 bytes, more than the 48 of a line"),
        ("mg1.b03.e000", "ab " * 30000, "the text takes 90000 bytes, more than"),
        ("mg2.b03.e000", "Line\n" * 10, "a page takes 11 lines, more than the 10"),
        ("mg2.b03.e000", "x" * 46, "a word takes 46 bytes, more than the 45 of a line"),
        ("mg2.b03.e000", "C:\\GAME", "A backslash starts an engine code in MG2"),
        ("mg2.b03.e000", "{x:5C}GAME", "{x:5C} starts no engine code, which hangs"),
    ],
    ids=[
        "no code",
        "placeholder of another game",
        "no glyph",
        "no double-byte glyph",
        "not in the HUD font",
        "double-byte in the HUD font",
        "lowercase in the HUD font",
        "MG1 word too long",
        "string too long",
        "MG2 page too long",
        "MG2 word too long",
        "MG2 backslash",
        "MG2 escape that hangs",
    ],
)
def test_translations_the_game_cannot_show_are_reported(
    unit_id: str, text: str, message: str, tmp_path: Path
) -> None:
    game = Game(unit_id[:3])
    export(game, tmp_path)
    translate(tmp_path, {unit_id: text})

    with pytest.raises(ValueError, match=message) as error:
        import_text_and_font(game, tmp_path)

    assert "text.po holds texts the game cannot show:\n" in str(error.value)


@pytest.mark.parametrize(
    ("unit_id", "text", "message"),
    [
        ("mg1.b03.e000", "x " * 25, "a line takes 50 bytes, more than the 48 of"),
        ("mg2.b03.e000", "x " * 24, "a line takes 48 bytes, more than the 47 of"),
        (
            "mg2.b03.e000",
            "Hi{wait}Snake",
            "{wait} hides the byte after it, so follow it with a line break, not 'S'",
        ),
    ],
    ids=["MG1 line too long", "MG2 line too long", "MG2 character after a wait"],
)
def test_japanese_translations_the_game_cannot_show_are_reported(
    unit_id: str, text: str, message: str, tmp_path: Path
) -> None:
    game = Game(unit_id[:3])
    export(game, tmp_path, font=text_font(japanese=True))
    translate(tmp_path, {unit_id: text})

    with pytest.raises(ValueError, match=message):
        import_text_and_font(game, tmp_path)


def test_japanese_waits_may_end_a_line_or_the_text(tmp_path: Path) -> None:
    export(Game.MG2, tmp_path, font=text_font(japanese=True))
    translate(tmp_path, {"mg2.b03.e000": "Hi{wait}\nSnake{wait}"})

    blocks, _ = import_text_and_font(Game.MG2, tmp_path)

    assert blocks[3].startswith(strings([b"Hi\\w\nSnake\\w"]))


def test_every_problem_of_a_document_is_reported_at_once(tmp_path: Path) -> None:
    export(Game.MG1, tmp_path)
    translate(tmp_path, {"mg1.b03.e000": "Ï", "mg1.b05.e000": "「", "mg1.b06.e000": "ż"})

    with pytest.raises(ValueError) as error:
        import_text_and_font(Game.MG1, tmp_path)

    assert [line[:12] for line in str(error.value).splitlines()[1:]] == [
        "mg1.b03.e000",
        "mg1.b05.e000",
        "mg1.b06.e000",
    ]


def test_the_opening_story_and_credits_of_mg2_may_have_longer_pages(
    tmp_path: Path,
) -> None:
    export(Game.MG2, tmp_path)
    translate(tmp_path, {"mg2.b17.e000": "Line\n" * 20})

    blocks, _ = import_text_and_font(Game.MG2, tmp_path)

    assert blocks[17] == strings([b"Line\n" * 20])


@pytest.mark.parametrize(
    ("game", "edit", "message"),
    [
        (
            Game.MG1,
            lambda d: d["styles"]["b03"].append(300),
            "Expected the styles of the blocks b03, b04, b05",
        ),
        (Game.MG1, lambda d: d["styles"].pop("b15"), "Expected the styles"),
        (
            Game.MG2,
            lambda d: d["strings"].update(b00="1"),
            "Expected the string counts",
        ),
        (
            Game.MG1,
            lambda d: d["warps"][0].update(params="ff"),
            "Warp point 0: Its parameters take 1 bytes, not 4",
        ),
        (
            Game.MG1,
            lambda d: d["warps"][1].update(x=70000),
            "Warp point 1: Its x is 70000, not a number from 0 to 65535",
        ),
        (
            Game.MG1,
            lambda d: d["warps"][1].update(name="ż"),
            r"Warp point 1: 'ż' \(U\+017C\) has no code",
        ),
        (Game.MG1, lambda d: d.pop("styles"), r"text\.json: missing 'styles'"),
    ],
)
def test_text_json_edits_the_game_cannot_take_are_reported(
    game: Game, edit: Callable[[Any], object], message: str, tmp_path: Path
) -> None:
    export(game, tmp_path)
    edit_json(tmp_path / "text.json", edit)

    with pytest.raises(ValueError, match=message):
        import_text_and_font(game, tmp_path)


def test_text_sections_without_all_their_blocks_are_refused(tmp_path: Path) -> None:
    with pytest.raises(FormatError, match="The mg1 text has 17 blocks, not 16"):
        export_text_and_font(Game.MG1, MG1_BLOCKS[:16], PAGES, tmp_path, TranslationFormat.PO)
