"""The texts of the MSX games and their exchange with translation tools.

The text section is a list of blocks whose kind is fixed by their index: lists
of strings, each a u16 BE length and its bytes (after a style byte in MG1), the
MG1 warp-point list, and MG1 tables that hold no text. The engine finds a string
by its position, so a translation keeps the number and order of the strings.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from mgtools.binary import BinaryReader, BinaryWriter, ByteOrder
from mgtools.errors import FormatError, located
from mgtools.fileio import convert_json, is_index, write_atomically, write_json
from mgtools.msx.charset import EU_CHARMAP, JP_CHARMAP, Charmap, Charset
from mgtools.msx.display import display_problems, translator_notes
from mgtools.msx.font import Font, decode_font, encode_font
from mgtools.msx.font_editable import export_font, import_font
from mgtools.msx.game import Game
from mgtools.translation import (
    TranslationFormat,
    Unit,
    export_units,
    find_document,
    read_document,
)

_TEXTS = "text"
_LAYOUT = "text.json"
_BLOCK_COUNTS = {Game.MG1: 17, Game.MG2: 24}
_STRING_BLOCKS = {Game.MG1: (3, 4, 5, 6, 7, 8, 9, 13, 14, 15), Game.MG2: range(24)}
_MG1_WARPS = 12
_WARP_RANGES = {"x": 0x10000, "y": 0x10000, "flag": 0x100}

_SHOWN_PROBLEMS = 20


@dataclass(frozen=True, slots=True)
class Entry:
    """A string of a text block, with its style byte in MG1."""

    data: bytes
    style: int | None


@dataclass(frozen=True, slots=True)
class Warp:
    """A debug warp point of MG1."""

    params: bytes
    name: bytes
    x: int
    y: int
    flag: int


def export_text_and_font(
    game: Game,
    text_blocks: list[bytes],
    font_pages: list[bytes],
    directory: Path,
    fmt: TranslationFormat,
    charmap: Charmap | None = None,
    *,
    separate_glyphs: bool = False,
) -> None:
    """Write a text section for translation tools and a font section as images.

    Args:
        game: The game of the sections.
        text_blocks: The blocks of the text section.
        font_pages: The pages of the font section.
        directory: The folder to write to.
        fmt: The format of the text for translation tools.
        charmap: The characters of the single-byte codes, None for those of the release.
        separate_glyphs: Whether to save each glyph as its own image instead of a PNG per page.
    """
    if len(text_blocks) != _BLOCK_COUNTS[game]:
        msg = f"The {game} text has {_BLOCK_COUNTS[game]} blocks, not {len(text_blocks)}"
        raise FormatError(msg)
    font = decode_font(font_pages)
    japanese = _is_japanese(font)
    if charmap is None:
        charmap = JP_CHARMAP if japanese else EU_CHARMAP
    charset = Charset(game, charmap)
    units: list[Unit] = []
    styles: dict[str, list[int | None]] = {}
    warps: list[dict[str, Any]] = []
    used: set[int] = set()
    for block, data in enumerate(text_blocks):
        if block not in _STRING_BLOCKS[game]:
            if block == _MG1_WARPS:
                warps = [_warp_json(warp, charset) for warp in _decode_warps(data)]
            else:
                write_atomically(directory / _table(block), data)
            continue
        entries = _decode_entries(data, styled=game is Game.MG1)
        styles[f"b{block:02d}"] = [entry.style for entry in entries]
        for number, entry in enumerate(entries):
            text = charset.decode(entry.data)
            notes = translator_notes(
                charset, font.pages[0], japanese, block, number, entry.data, entry.style
            )
            units.append(Unit(_id(game, block, number), text, notes))
            used.update(_double_byte_codes(charset, entry.data))
    if game is Game.MG1:
        layout: dict[str, Any] = {"styles": styles, "warps": warps}
    else:
        layout = {"strings": {block: len(entries) for block, entries in styles.items()}}
    document = export_units(
        units, fmt, original=f"{game} text", source_language="ja" if japanese else "und"
    )
    write_atomically(directory / f"{_TEXTS}{fmt.suffix}", document)
    write_json(directory / _LAYOUT, layout)
    export_font(_with_default_code(font, used), charset, directory, separate_glyphs=separate_glyphs)


def import_text_and_font(game: Game, directory: Path) -> tuple[list[bytes], list[bytes]]:
    """Read the sections export_text_and_font wrote, if the game can show the text.

    Args:
        game: The game of the sections.
        directory: The folder export_text_and_font wrote.
    """
    font, charset = import_font(game, directory)
    japanese = _is_japanese(font)
    strings, warps = convert_json(
        directory / _LAYOUT,
        lambda layout: (_strings(game, layout), _warps(game, layout, charset)),
    )
    path = find_document(directory, _TEXTS)
    ids = [_id(game, block, n) for block, s in strings.items() for n in range(len(s))]
    texts = read_document(path, ids)
    problems: list[str] = []
    blocks: list[bytes] = []
    for block in range(_BLOCK_COUNTS[game]):
        if block not in strings:
            if block == _MG1_WARPS:
                blocks.append(_encode_warps(warps))
            else:
                blocks.append((directory / _table(block)).read_bytes())
            continue
        entries = []
        for number, style in enumerate(strings[block]):
            unit_id = _id(game, block, number)
            try:
                data = _encoded(texts[unit_id], charset)
            except ValueError as error:
                problems.append(f"{unit_id}: {error}")
                continue
            found = display_problems(charset, font, japanese, block, number, data)
            problems += (f"{unit_id}: {problem}" for problem in dict.fromkeys(found))
            entries.append(Entry(data, style))
        blocks.append(_encode_entries(entries))
    if problems:
        shown = "\n".join(problems[:_SHOWN_PROBLEMS])
        more = len(problems) - _SHOWN_PROBLEMS
        msg = f"{path} holds texts the game cannot show:\n{shown}"
        raise ValueError(msg + (f"\nand {more} more" if more > 0 else ""))
    return blocks, encode_font(font)


def _is_japanese(font: Font) -> bool:
    # Only the Japanese release has sized font pages.
    return font.pages[1].v is not None


def _id(game: Game, block: int, number: int) -> str:
    """Return the translation unit id of a string, such as mg1.b03.e000."""
    return f"{game}.b{block:02d}.e{number:03d}"


def _table(block: int) -> str:
    """Return the path of a block that holds no text, relative to the export folder."""
    return f"text/b{block:02d}.bin"


def _decode_entries(data: bytes, *, styled: bool) -> list[Entry]:
    reader = BinaryReader(data, ByteOrder.BIG)
    entries = []
    while reader.remaining:
        style = reader.u8() if styled else None
        entries.append(Entry(reader.read(reader.u16()), style))
    return entries


def _encode_entries(entries: Iterable[Entry]) -> bytes:
    writer = BinaryWriter(ByteOrder.BIG)
    for entry in entries:
        if entry.style is not None:
            writer.u8(entry.style)
        writer.u16(len(entry.data))
        writer.write(entry.data)
    return writer.getvalue()


def _decode_warps(data: bytes) -> list[Warp]:
    reader = BinaryReader(data, ByteOrder.BIG)
    warps = []
    while reader.remaining:
        params, name = reader.read(4), reader.read(reader.u16())
        warps.append(Warp(params, name, *reader.unpack("HHB")))
    return warps


def _encode_warps(warps: Iterable[Warp]) -> bytes:
    writer = BinaryWriter(ByteOrder.BIG)
    for warp in warps:
        writer.write(warp.params)
        writer.u16(len(warp.name))
        writer.write(warp.name)
        writer.pack("HHB", warp.x, warp.y, warp.flag)
    return writer.getvalue()


def _warp_json(warp: Warp, charset: Charset) -> dict[str, Any]:
    return {
        "params": warp.params.hex(),
        "name": charset.decode(warp.name),
        "x": warp.x,
        "y": warp.y,
        "flag": warp.flag,
    }


def _warps(game: Game, layout: dict[str, Any], charset: Charset) -> list[Warp]:
    """Return the warp points of a text.json, refusing values the game cannot store.

    Args:
        game: The game of the text; MG2 has no warp points.
        layout: The text.json document.
        charset: The characters of the warp point names.
    """
    warps = []
    for number, item in enumerate(layout["warps"] if game is Game.MG1 else []):
        with located(f"Warp point {number}"):
            params = bytes.fromhex(item["params"])
            if len(params) != 4:
                msg = f"Its parameters take {len(params)} bytes, not 4"
                raise ValueError(msg)
            for key, count in _WARP_RANGES.items():
                if not is_index(item[key], count):
                    msg = f"Its {key} is {item[key]!r}, not a number from 0 to {count - 1}"
                    raise ValueError(msg)
            name = _encoded(item["name"], charset)
            warps.append(Warp(params, name, item["x"], item["y"], item["flag"]))
    return warps


def _strings(game: Game, layout: dict[str, Any]) -> dict[int, list[int | None]]:
    """Return the style of each string by block, None for every string of MG2."""
    if game is Game.MG1:
        found = {key: list(styles) for key, styles in layout["styles"].items()}
        valid = all(is_index(s, 0x100) for v in found.values() for s in v)
    else:
        counts = layout["strings"]
        valid = all(type(count) is int for count in counts.values())
        found = {key: [None] * count for key, count in counts.items()} if valid else {}
    blocks = {f"b{block:02d}": block for block in _STRING_BLOCKS[game]}
    if found.keys() != blocks.keys() or not valid:
        what = "styles" if game is Game.MG1 else "string counts"
        msg = f"Expected the {what} of the blocks {', '.join(blocks)}"
        raise ValueError(msg)
    return {blocks[key]: found[key] for key in blocks}


def _encoded(text: str, charset: Charset) -> bytes:
    """Return the bytes of a text, refusing one longer than a string can be."""
    data = charset.encode(text)
    if len(data) > 0xFFFF:
        msg = f"the text takes {len(data)} bytes, more than the 65535 of a string"
        raise ValueError(msg)
    return data


def _double_byte_codes(charset: Charset, data: bytes) -> Iterator[int]:
    for raw, _ in charset.characters(data):
        if len(raw) == 2 and raw[0] >= 0x80:
            yield int.from_bytes(raw)


def _with_default_code(font: Font, used: set[int]) -> Font:
    """Name glyph 0 of page 4 after the code the text draws it for, if any."""
    unmapped = sorted(used - {glyph.code for glyph in font.double_byte})
    if not font.double_byte or font.double_byte[0].code is not None or not unmapped:
        return font
    first = replace(font.double_byte[0], code=unmapped[0])
    return replace(font, double_byte=(first, *font.double_byte[1:]))
