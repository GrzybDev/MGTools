"""The editable form of an MSX font: font.json and PNG images of its glyphs.

font.json holds the charmap, the width of each glyph, what the images cannot
show of a page, and the character of each glyph of page 4. The glyphs are drawn
in a PNG per page, or each in a PNG of its own in a folder per page; font.json
then names each page's folder and each glyph's image.
"""

import re
from collections.abc import Iterator, Sequence
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
_DOUBLE_BYTE_BOX = (DOUBLE_BYTE_SIZE, DOUBLE_BYTE_SIZE)
_OUTSIDE, _NO_GLYPH = 4, 5
_PALETTE = GREY_PALETTE + bytes((40, 40, 112, 112, 32, 32))


def export_font(
    font: Font, charset: Charset, directory: Path, *, separate_glyphs: bool = False
) -> None:
    """Write a font as font.json and PNG images, with the charmap of its codes.

    Args:
        font: The font to write.
        charset: The characters of the codes, whose charmap font.json keeps.
        directory: The folder to write to.
        separate_glyphs: Whether to save each glyph as its own image instead of a PNG per page.
    """
    characters = [
        None if glyph.code is None else charset.decode(glyph.code.to_bytes(2))
        for glyph in font.double_byte
    ]
    write_json(
        directory / _DOCUMENT,
        {
            "charmap": {f"{code:02X}": c for code, c in sorted(charset.charmap.items())},
            "pages": [
                _export_page(index, page, charset.charmap, directory, separate_glyphs)
                for index, page in enumerate(font.pages)
            ],
            "double_byte": characters,
            **_export_double_byte(font.double_byte, characters, directory, separate_glyphs),
        },
    )


def import_font(game: Game, directory: Path) -> tuple[Font, Charset]:
    """Read a font and its charmap written by export_font, from the images font.json names.

    Args:
        game: The game of the font, which decides the placeholders of its charset.
        directory: The folder export_font wrote.
    """
    charset, layouts, codes, images = convert_json(
        directory / _DOCUMENT, lambda document: _read_document(game, document, directory)
    )
    pages = tuple(_read_page(i, layout, directory) for i, layout in enumerate(layouts))
    if images is None:
        glyphs = read_glyph_sheet(
            directory / _png(4), len(codes), DOUBLE_BYTE_SIZE, _DOUBLE_BYTE_COLUMNS
        )
    else:
        glyphs = [pack_2bpp(_glyph_pixels(path, _DOUBLE_BYTE_BOX)) for path in images]
    return Font(pages, tuple(map(DoubleByteGlyph, codes, glyphs, strict=True))), charset


def read_charmap(path: Path) -> Charmap:
    """Read the charmap of a font.json that export_font wrote.

    Args:
        path: The font.json to read.
    """
    return convert_json(path, _charmap)


@dataclass(frozen=True, slots=True)
class _Layout:
    """What font.json gives of a proportional page, which its images complete."""

    widths: dict[int, int]
    pad_bits: dict[int, int]
    floor_packed: bool
    v: int | None
    images: dict[int, Path] | None
    """The image of each glyph, or None when the page is drawn in one image."""


def _png(index: int) -> str:
    """Return the path of the image of a font page, relative to the export folder."""
    return f"font/page{index}.png"


def _folder(index: int) -> str:
    """Return the folder of the glyph images of a font page, relative to the export folder."""
    return f"font/page{index}"


def _export_page(
    index: int, page: Page, charmap: Charmap, directory: Path, separate_glyphs: bool
) -> dict[str, Any]:
    """Write the images of a proportional page and return its entry of font.json."""
    pad_bits = {
        f"{code:02X}": bits for code in page.glyphs if (bits := _pad_bits(index, page, code))
    }
    entry: dict[str, Any] = {
        **({"floor_packed": True} if page.floor_packed else {}),
        **({} if page.v is None else {"v": page.v}),
        **({"pad_bits": pad_bits} if pad_bits else {}),
        "widths": {f"{c:02X}": page.glyphs[c].width for c in sorted(page.glyphs)},
    }
    if not separate_glyphs:
        write_png(directory / _png(index), _page_image(index, page))
        return entry
    images: dict[str, str] = {}
    for code, pixels in _drawn_pixels(index, page):
        name = _image_name(chr(code) if code < 0x7F else charmap.get(code), code)
        size = (page.glyphs[code].width, HEIGHTS[index])
        write_png(directory / _folder(index) / name, grey_image(pixels, size))
        images[f"{code:02X}"] = name
    return {"glyphs": _folder(index), **entry, "images": images}


def _export_double_byte(
    glyphs: Sequence[DoubleByteGlyph],
    characters: Sequence[str | None],
    directory: Path,
    separate_glyphs: bool,
) -> dict[str, Any]:
    """Write the images of page 4 and return what font.json names of them."""
    if not separate_glyphs:
        sheet = glyph_sheet(
            [glyph.data for glyph in glyphs], DOUBLE_BYTE_SIZE, _DOUBLE_BYTE_COLUMNS, _NO_GLYPH
        )
        sheet.putpalette(_PALETTE)
        write_png(directory / _png(4), sheet)
        return {}
    names: list[str] = []
    for index, (glyph, character) in enumerate(zip(glyphs, characters, strict=True)):
        if glyph.code is not None:
            name = _image_name(character, glyph.code)
        else:
            # Glyph 0 draws every code no glyph is mapped to; no code draws the others.
            name = "fallback.png" if index == 0 else f"unused-{index}.png"
        pixels = unpack_2bpp(glyph.data, DOUBLE_BYTE_SIZE * DOUBLE_BYTE_SIZE)
        write_png(directory / _folder(4) / name, grey_image(pixels, _DOUBLE_BYTE_BOX))
        names.append(name)
    return {"double_byte_glyphs": _folder(4), "double_byte_images": names}


def _image_name(character: str | None, code: int) -> str:
    """Name the image of a glyph after its character, or after its code if it has none."""
    if character is not None and len(character) == 1:
        return f"U+{ord(character):04X}.png"
    return f"code-{code:02X}.png"


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
    game: Game, document: dict[str, Any], directory: Path
) -> tuple[Charset, list[_Layout], list[int | None], list[Path] | None]:
    """Return the charset, the page layouts, and the codes and any images of page 4."""
    charset = Charset(game, _charmap(document))
    layouts = [_read_layout(i, document["pages"][i], directory) for i in range(4)]
    codes: list[int | None] = []
    for character in document["double_byte"]:
        code = None if character is None else _double_byte_code(character, charset)
        if code is not None and code in codes:
            msg = f"Page 4 lists {character!r} twice"
            raise ValueError(msg)
        codes.append(code)
    images = None
    if "double_byte_glyphs" in document:
        folder = directory / document["double_byte_glyphs"]
        images = [folder / name for name in document["double_byte_images"]]
        if len(images) != len(codes):
            msg = (
                f"double_byte_images names {len(images)} images for the {len(codes)} "
                "glyphs of double_byte"
            )
            raise ValueError(msg)
    return charset, layouts, codes, images


def _charmap(document: dict[str, Any]) -> Charmap:
    """Return the charmap of a font.json, refusing codes that are not free."""
    charmap = {_code(key): c for key, c in document["charmap"].items()}
    character_codes(charmap)
    return charmap


def _read_layout(index: int, document: dict[str, Any], directory: Path) -> _Layout:
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
    images = None
    if "glyphs" in document:
        folder = directory / document["glyphs"]
        images = {_code(key): folder / name for key, name in document["images"].items()}
        if unmatched := images.keys() ^ widths.keys():
            code = min(unmatched)
            what = "an image but no width" if code in images else "a width but no image"
            msg = f"Page {index} gives {code:02X} {what}"
            raise ValueError(msg)
    return _Layout(widths, pad_bits, floor_packed, v, images)


def _read_page(index: int, layout: _Layout, directory: Path) -> Page:
    """Read a proportional page from its images, refusing pixels the game draws otherwise."""
    shown = dict(_shown_glyphs(index, layout, directory))
    glyphs: dict[int, Glyph] = {}
    for code, (_, pixels) in shown.items():
        data = pack_2bpp(pixels)
        if layout.floor_packed:
            data = data[: len(pixels) // 4]
        if bits := layout.pad_bits.get(code):
            data = data[:-1] + bytes((data[-1] | bits,))
        glyphs[code] = Glyph(layout.widths[code], data)
    page = Page(glyphs, layout.floor_packed, layout.v)
    for code, pixels in _drawn_pixels(index, page):
        where, image_pixels = shown[code]
        if pixels != image_pixels:
            msg = (
                f"{where}: the game draws the last two pixels of a glyph of "
                f"floor-packed page {index} from the next glyph, not as the image "
                f"shows them; remove floor_packed from page {index} in {_DOCUMENT} "
                "to keep them"
            )
            raise ValueError(msg)
    return page


def _shown_glyphs(
    index: int, layout: _Layout, directory: Path
) -> Iterator[tuple[int, tuple[str, bytes]]]:
    """Yield the pixels each glyph of a page shows by code, with where they are drawn."""
    height = HEIGHTS[index]
    if layout.images is not None:
        for code, width in layout.widths.items():
            path = layout.images[code]
            yield code, (str(path), _glyph_pixels(path, (width, height)))
        return
    path = directory / _png(index)
    image = read_image(path, (_COLUMNS * _MAX_WIDTH, _ROWS * height))
    for code, width in layout.widths.items():
        left, top = _cell(index, code)
        where = f"{path}, glyph {code:02X}"
        with located(where):
            pixels = grey_pixels(image, (left, top, left + width, top + height))
        yield code, (where, pixels)


def _glyph_pixels(path: Path, size: tuple[int, int]) -> bytes:
    """Return the 2-bit values of the image of one glyph, refusing an image of another size."""
    image = read_image(path, size)
    with located(path):
        return grey_pixels(image)


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
