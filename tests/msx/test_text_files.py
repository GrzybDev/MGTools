import codecs
import re
from pathlib import Path

import pytest
from lxml import etree

from mgtools.fileio import read_json
from mgtools.msx.charset import JP_CHARMAP
from mgtools.msx.container import Container, Leaf, Node, decode_node
from mgtools.msx.game import Game
from mgtools.msx.text import export_text_and_font, import_text_and_font
from mgtools.translation import TranslationFormat, import_units
from tests.editing import with_targets

GAMES = {77: Game.MG1, 49: Game.MG2}
SECTIONS = {Game.MG1: (72, 75), Game.MG2: (2, 48)}
PLACEHOLDER = re.compile(r"(\{[^{}]*\})")
KANA = re.compile("[\N{HIRAGANA LETTER SMALL A}-\N{KATAKANA DIGRAPH KOTO}]")


def leaves(node: Node) -> list[bytes]:
    assert isinstance(node, Container)
    assert all(isinstance(child, Leaf) for child in node.children)
    return [child.data for child in node.children if isinstance(child, Leaf)]


def sections(path: Path) -> tuple[Game, list[bytes], list[bytes]]:
    """Return the game of a resource file and its text blocks and font pages.

    Args:
        path: The resource file.
    """
    root = decode_node(path.read_bytes())
    assert isinstance(root, Container)
    game = GAMES[len(root.children)]
    text, font = (root.children[index] for index in SECTIONS[game])
    return game, leaves(text), leaves(font)


def changed(text: str) -> str:
    """Translate a text by changing its ASCII letters and adding to its start.

    Args:
        text: The text to translate.
    """
    parts = PLACEHOLDER.split(text)
    return "1" + "".join(
        p if PLACEHOLDER.fullmatch(p) else codecs.encode(p, "rot13") for p in parts
    )


@pytest.mark.parametrize("separate_glyphs", [False, True], ids=["page images", "glyph images"])
def test_every_text_and_font_imports_back_byte_for_byte(
    resource_files: list[Path], separate_glyphs: bool, subtests: pytest.Subtests, tmp_path: Path
) -> None:
    for index, path in enumerate(resource_files):
        with subtests.test(path.as_posix()):
            game, blocks, pages = sections(path)
            for fmt in TranslationFormat:
                directory = tmp_path / f"{index}-{fmt}"

                export_text_and_font(
                    game, blocks, pages, directory, fmt, separate_glyphs=separate_glyphs
                )

                assert import_text_and_font(game, directory) == (blocks, pages)


def test_every_text_takes_a_translation_and_reads_back_as_translated(
    resource_files: list[Path], subtests: pytest.Subtests, tmp_path: Path
) -> None:
    formats = list(TranslationFormat)
    for index, path in enumerate(resource_files):
        with subtests.test(path.as_posix()):
            game, blocks, pages = sections(path)
            fmt = formats[index % len(formats)]
            document = tmp_path / str(index) / f"text{fmt.suffix}"
            export_text_and_font(game, blocks, pages, document.parent, fmt)
            sources = import_units(document.read_bytes())
            translated = {unit_id: changed(text) for unit_id, text in sources.items()}
            document.write_bytes(with_targets(document.read_bytes(), fmt, translated))

            new_blocks, new_pages = import_text_and_font(game, document.parent)
            again = tmp_path / f"{index}-again"
            export_text_and_font(game, new_blocks, new_pages, again, fmt)

            assert new_pages == pages
            assert import_units((again / f"text{fmt.suffix}").read_bytes()) == translated


def test_japanese_files_read_as_japanese(
    steam_dir: Path, subtests: pytest.Subtests, tmp_path: Path
) -> None:
    files = sorted(steam_dir.glob("jp/stage/mg?/cache/**/japanese.raw"))
    assert {sections(path)[0] for path in files} == set(Game)
    for index, path in enumerate(files):
        with subtests.test(path.as_posix()):
            game, blocks, pages = sections(path)
            directory = tmp_path / str(index)

            export_text_and_font(game, blocks, pages, directory, TranslationFormat.XLIFF2)

            root = etree.fromstring((directory / "text.xlf").read_bytes())
            texts = import_units((directory / "text.xlf").read_bytes()).values()
            font = read_json(directory / "font.json")
            assert root.get("srcLang") == "ja"
            assert sum(bool(KANA.search(text)) for text in texts) > len(texts) / 2
            assert not any("{x:" in text or "{sjis:" in text for text in texts)
            assert font["charmap"] == {f"{c:02X}": t for c, t in JP_CHARMAP.items()}
            assert len(font["double_byte"]) > 400
