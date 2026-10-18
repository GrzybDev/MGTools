"""The editable form of an MSX font: a PNG of each page and font.json.

font.json holds the charmap, the width of each glyph, what the images cannot
show of a page, and the character of each glyph of page 4.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from mgtools.bitmap import (
    GREY_PALETTE,
    glyph_sheet,
    grey_image,
    grey_pixels,
    pack_2bpp,
    read_glyph_sheet,
    unpack_2bpp,
)
from mgtools.errors import located
from mgtools.fileio import (
    convert_json,
    is_index,
    read_image,
    write_json,
    write_png,
)
from mgtools.msx.charset import Charmap, Charset, character_codes
from mgtools.msx.font import (
    CODES,
    DOUBLE_BYTE_SIZE,
    HEIGHTS,
    DoubleByteGlyph,
    Font,
    Glyph,
    Page,
)
from mgtools.msx.game import Game

_DOCUMENT = "font.json"
_COLUMNS = 16
_ROWS = len(CODES) // _COLUMNS
# The images give each code a cell as wide as the widest glyph a slot can hold.
_MAX_WIDTH = 64
_DOUBLE_BYTE_COLUMNS = 32
_OUTSIDE, _NO_GLYPH = 4, 5
_PALETTE = GREY_PALETTE + bytes((40, 40, 112, 112, 32, 32))


def export_font(font: Font, charset: Charset, directory: Path) -> None:
    """Write a font as a PNG per page and font.json, with the charmap of its codes.

    Args:
        font: The font to write.
        charset: The characters of the codes, whose charmap font.json keeps.
        directory: The folder to write to.
    """
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(font.pages):
        write_png(directory / _png(index), _page_image(index, page))
        pad_bits = {
            f"{code:02X}": bits for code in page.glyphs if (bits := _pad_bits(index, page, code))
        }
        pages.append(
            {
                **({"floor_packed": True} if page.floor_packed else {}),
                **({} if page.v is None else {"v": page.v}),
                **({"pad_bits": pad_bits} if pad_bits else {}),
                "widths": {f"{c:02X}": page.glyphs[c].width for c in sorted(page.glyphs)},
            }
        )
    sheet = glyph_sheet(
        [glyph.data for glyph in font.double_byte],
        DOUBLE_BYTE_SIZE,
        _DOUBLE_BYTE_COLUMNS,
        _NO_GLYPH,
    )
    sheet.putpalette(_PALETTE)
    write_png(directory / _png(4), sheet)
    write_json(
        directory / _DOCUMENT,
        {
            "charmap": {f"{code:02X}": c for code, c in sorted(charset.charmap.items())},
            "pages": pages,
            "double_byte": [
                None if g.code is None else charset.decode(g.code.to_bytes(2))
                for g in font.double_byte
            ],
        },
    )


def import_font(game: Game, directory: Path) -> tuple[Font, Charset]:
    """Read a font and its charmap written by export_font.

    Args:
        game: The game of the font, which decides the placeholders of its charset.
        directory: The folder export_font wrote.
    """
    charset, layouts, codes = convert_json(
        directory / _DOCUMENT, lambda document: _read_document(game, document)
    )
    pages = tuple(_read_page(i, layout, directory) for i, layout in enumerate(layouts))
    glyphs = read_glyph_sheet(
        directory / _png(4), len(codes), DOUBLE_BYTE_SIZE, _DOUBLE_BYTE_COLUMNS
    )
    return Font(pages, tuple(map(DoubleByteGlyph, codes, glyphs, strict=True))), charset


def read_charmap(path: Path) -> Charmap:
    """Read the charmap of a font.json that export_font wrote.

    Args:
        path: The font.json to read.
    """
    return convert_json(path, _charmap)


@dataclass(frozen=True, slots=True)
class _Layout:
    """What font.json gives of a proportional page, which its image completes."""

    widths: dict[int, int]
    pad_bits: dict[int, int]
    floor_packed: bool
    v: int | None


def _png(index: int) -> str:
    """Return the path of the image of a font page, relative to the export folder."""
    return f"font/page{index}.png"


def _new_image(size: tuple[int, int]) -> Image.Image:
    """Return an image of the font palette whose every pixel shows no glyph."""
    image = Image.new("P", size, _NO_GLYPH)
    image.putpalette(_PALETTE)
    return image


def _cell(index: int, code: int) -> tuple[int, int]:
    """Return the top left corner of the cell of a code in the image of a page."""
    row, column = divmod(CODES.index(code), _COLUMNS)
    return column * _MAX_WIDTH, row * HEIGHTS[index]


def _page_image(index: int, page: Page) -> Image.Image:
    height = HEIGHTS[index]
    image = _new_image((_COLUMNS * _MAX_WIDTH, _ROWS * height))
    for code, pixels in _drawn_pixels(index, page):
        left, top = _cell(index, code)
        image.paste(_OUTSIDE, (left, top, left + _MAX_WIDTH, top + height))
        size = (page.glyphs[code].width, height)
        image.paste(grey_image(pixels, size), (left, top))
    return image


def _drawn_pixels(index: int, page: Page) -> Iterator[tuple[int, bytes]]:
    """Yield the pixels the engine draws, ending a floor-packed glyph from the next."""
    codes = sorted(page.glyphs)
    stream = b"".join(page.glyphs[code].data for code in codes) + b"\0"
    offset = 0
    for code in codes:
        glyph = page.glyphs[code]
        end = offset + len(glyph.data)
        yield code, unpack_2bpp(stream[offset : end + 1], glyph.width * HEIGHTS[index])
        offset = end


def _pad_bits(index: int, page: Page, code: int) -> int:
    """Return the bits after the last pixel of a ceiling-packed glyph."""
    glyph = page.glyphs[code]
    unused = -glyph.width * HEIGHTS[index] % 4
    return 0 if page.floor_packed else glyph.data[-1] & (4**unused - 1)


def _read_document(
    game: Game, document: dict[str, Any]
) -> tuple[Charset, list[_Layout], list[int | None]]:
    """Return the charset, the page layouts and the page 4 codes a font.json gives."""
    charset = Charset(game, _charmap(document))
    layouts = [_read_layout(index, document["pages"][index]) for index in range(4)]
    codes: list[int | None] = []
    for character in document["double_byte"]:
        code = None if character is None else _double_byte_code(character, charset)
        if code is not None and code in codes:
            msg = f"Page 4 lists {character!r} twice"
            raise ValueError(msg)
        codes.append(code)
    return charset, layouts, codes


def _charmap(document: dict[str, Any]) -> Charmap:
    """Return the charmap of a font.json, refusing codes that are not free."""
    charmap = {_code(key): c for key, c in document["charmap"].items()}
    character_codes(charmap)
    return charmap


def _read_layout(index: int, document: dict[str, Any]) -> _Layout:
    """Return what font.json gives of a page, refusing values the page cannot store."""
    floor_packed = document.get("floor_packed", False) is True
    v = document.get("v")
    if v is not None and not is_index(v, 0x100):
        msg = f"Page {index} has the constant {v!r}, not a byte"
        raise ValueError(msg)
    widths = {_code(key): width for key, width in document["widths"].items()}
    for code, width in widths.items():
        if not is_index(width, _MAX_WIDTH + 1) or width == 0:
            msg = f"Page {index} gives {code:02X} the width {width!r}, not 1 to 64"
            raise ValueError(msg)
    pad_bits = {_code(key): bits for key, bits in document.get("pad_bits", {}).items()}
    for code, bits in pad_bits.items():
        if code not in widths:
            msg = f"Page {index} gives pad bits to {code:02X}, which has no glyph"
            raise ValueError(msg)
        unused = -widths[code] * HEIGHTS[index] % 4
        if floor_packed or not isinstance(bits, int) or not 0 < bits < 4**unused:
            msg = f"Page {index} gives {code:02X} pad bits it has no room for"
            raise ValueError(msg)
    return _Layout(widths, pad_bits, floor_packed, v)


def _read_page(index: int, layout: _Layout, directory: Path) -> Page:
    """Read a proportional page from its image, refusing pixels the game draws otherwise."""
    height = HEIGHTS[index]
    path = directory / _png(index)
    image = read_image(path, (_COLUMNS * _MAX_WIDTH, _ROWS * height))
    glyphs: dict[int, Glyph] = {}
    shown: dict[int, bytes] = {}
    for code, width in layout.widths.items():
        left, top = _cell(index, code)
        with located(f"{path}, glyph {code:02X}"):
            shown[code] = grey_pixels(image, (left, top, left + width, top + height))
        data = pack_2bpp(shown[code])
        if layout.floor_packed:
            data = data[: len(shown[code]) // 4]
        if bits := layout.pad_bits.get(code):
            data = data[:-1] + bytes((data[-1] | bits,))
        glyphs[code] = Glyph(width, data)
    page = Page(glyphs, layout.floor_packed, layout.v)
    for code, pixels in _drawn_pixels(index, page):
        if pixels != shown[code]:
            msg = (
                f"{path}, glyph {code:02X}: the game draws the last two pixels of "
                f"a glyph of floor-packed page {index} from the next glyph, not as "
                f"the image shows them; remove floor_packed from page {index} in "
                f"{_DOCUMENT} to keep them"
            )
            raise ValueError(msg)
    return page


def _double_byte_code(character: str, charset: Charset) -> int:
    data = charset.encode(character)
    if len(data) != 2 or data[0] < 0x80:
        msg = f"Page 4 lists {character!r}, not a double-byte character"
        raise ValueError(msg)
    return int.from_bytes(data)


def _code(key: str) -> int:
    """Return the code a key of font.json names in hex, such as 7F."""
    if not re.fullmatch("[2-9A-Fa-f][0-9A-Fa-f]", key):
        msg = f"{key!r} is not a code from 20 to FF"
        raise ValueError(msg)
    return int(key, 16)
