import struct
from collections.abc import Callable

import pytest

from mgtools.errors import FormatError
from mgtools.msx.font import Font, Page, decode_font, encode_font
from tests.msx.samples import FONT, PADDED_FONT, glyph


def slot(page: bytes, code: int) -> int:
    word: int = struct.unpack_from("<I", page, (code - 0x1E) * 4)[0]
    return word


def with_slot(page: bytes, code: int, word: int) -> bytes:
    offset = (code - 0x1E) * 4
    return page[:offset] + struct.pack("<I", word) + page[offset + 4 :]


@pytest.mark.parametrize("font", [FONT, PADDED_FONT], ids=["font", "padded"])
def test_fonts_decode_from_the_pages_they_encode_to(font: Font) -> None:
    assert decode_font(encode_font(font)) == font


def test_pages_encode_to_the_layout_the_engine_reads() -> None:
    legacy, sized, floor_packed, _, double_byte = encode_font(FONT)
    indices = struct.unpack_from(">32768H", double_byte, 4)

    assert len(legacy) == 20480
    assert legacy[:8] == bytes(8)
    assert slot(legacy, 0x20) == 0 | 3 << 20
    assert slot(legacy, 0x41) == 24 | 6 << 20
    assert slot(legacy, 0x42) == 0xFFF0 << 16 | 24 + 42
    assert legacy[0x388 + 24 : 0x388 + 66] == FONT.pages[0].glyphs[0x41].data
    assert not any(legacy[0x388 + 96 :])
    assert len(sized) == 0x388 + 9 + 15 + 6
    assert struct.unpack_from("<II", sized) == (12 << 24 | 0x388, len(sized))
    assert slot(sized, 0x42) == 9 | 4 << 20 | 3 << 26
    assert slot(sized, 0xFF) == 24 | 1 << 20 | 3 << 26
    assert slot(floor_packed, 0x43) == 3 * 18 // 4 | 1 << 20
    assert slot(floor_packed, 0x45) == 3 * 18 // 4 + 2 * 18 // 4 | 4 << 20
    assert double_byte[:4] == bytes.fromhex("0000 0090")
    assert {code: i for code, i in enumerate(indices, 0x8000) if i} == {0x82A0: 1, 0x8341: 2}
    assert double_byte[0x10004 + 144 : 0x10004 + 288] == FONT.double_byte[1].data


def test_legacy_pages_refuse_more_glyphs_than_they_have_room_for() -> None:
    crowded = Page({code: glyph(64, 24) for code in range(0x20, 0x55)})

    with pytest.raises(ValueError, match="page 0 take 20352 bytes of 19576"):
        encode_font(Font((crowded, *FONT.pages[1:]), FONT.double_byte))


type Damage = Callable[[list[bytes]], list[bytes]]

MIXED = Font(
    (
        *FONT.pages[:2],
        Page({0x41: glyph(3, 18), 0x43: glyph(3, 18, floor=True)}),
        Page({}),
    ),
    FONT.double_byte,
)


SIZED_WITHOUT_FF = Font(
    (FONT.pages[0], Page({0x20: glyph(3, 12)}, v=12), *FONT.pages[2:]),
    FONT.double_byte,
)


def damaged(page: int, change: Callable[[bytes], bytes]) -> Damage:
    def damage(pages: list[bytes]) -> list[bytes]:
        return [change(data) if i == page else data for i, data in enumerate(pages)]

    return damage


def grown(page: bytes) -> bytes:
    """Add a zero byte to a sized page, counted by its size.

    Args:
        page: The encoded sized page.
    """
    return page[:4] + struct.pack("<I", len(page) + 1) + page[8:] + b"\0"


@pytest.mark.parametrize(
    ("damage", "message"),
    [
        (lambda pages: pages[:4], "A font has 5 pages, not 4"),
        (damaged(0, lambda p: p + b"\0"), "page 0 takes 20481 bytes, not 20480"),
        (damaged(0, lambda p: b"\1" + p[1:]), "page 0 has the unknown header 00000001"),
        (damaged(1, lambda p: p + b"\0"), "page 1 has the unknown header"),
        (damaged(0, lambda p: p[:-1] + b"\1"), "page 0 has data after its glyphs"),
        (
            lambda _: damaged(1, grown)(encode_font(SIZED_WITHOUT_FF)),
            "page 1 has data after its glyphs",
        ),
        (
            damaged(0, lambda p: with_slot(p, 0x21, 0xFFF0 << 16 | 25)),
            "page 0 gives 20 25 bytes for 96 pixels",
        ),
        (
            damaged(0, lambda p: with_slot(p, 0x41, 25 | 6 << 20)),
            "page 0 puts 41 at 25, not at 24",
        ),
        (
            damaged(0, lambda p: with_slot(p, 0x41, 24 | 6 << 20 | 1 << 26)),
            "page 0 gives 41 the unknown bits 1",
        ),
        (
            lambda _: encode_font(MIXED),
            "page 2 packs some glyphs to floor and others to ceiling",
        ),
        (damaged(4, lambda p: b"\0\1" + p[2:]), "page 4 has the unknown header"),
        (damaged(4, lambda p: p + bytes(5)), "page 4 ends with 5 bytes that are no"),
        (
            damaged(4, lambda p: p[:4] + struct.pack(">H", 3) + p[6:]),
            "page 4 maps 8000 to glyph 3, which it cannot",
        ),
        (
            damaged(4, lambda p: p[:4] + struct.pack(">H", 1) + p[6:]),
            "page 4 maps 82A0 to glyph 1, which it cannot",
        ),
    ],
)
def test_malformed_fonts_are_reported(damage: Damage, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        decode_font(damage(encode_font(FONT)))
