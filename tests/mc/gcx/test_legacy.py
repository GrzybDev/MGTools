import pytest

from mgtools.mc.gcx.legacy import decode_legacy, encode_legacy, glyphs_used

NARROW = chr(0xE000)
OPENING = chr(0xE001)
WEAPON = chr(0xE082)
WIDE_SPACE = chr(0x3000)


@pytest.mark.parametrize(
    ("data", "markup"),
    [
        (b"Go!\n", "Go!\n"),
        (b"Caf\x1f\x0f \x1f\x41Qu\x1f\x0f?", "Café ¿Qué?"),
        (b"\x81\x01\x81\x50\x81\x51", "ぁをん"),
        (b"\x82\x2b\x82\x51\x82\x52", "ニンヴ"),
        (b"\x83\x04 \x83\x01", f"{WEAPON} {WIDE_SPACE}"),
        (b"\xc3\x09\xa0\x7b\xe3\x08", f"{NARROW}。{OPENING}{{{NARROW}{OPENING}、"),
        (b"\x8c\x01\x8d\x02", "{8C01}{8D02}"),
        (b"\x80\x41\x1f\x0c\x83\x7f", "{8041}{1F0C}{837F}"),
        (b"{x}\x01\x7f", "{7B}x{7D}{01}{7F}"),
        (b"end\x8c", "end{8C}"),
    ],
)
def test_strings_read_as_markup_and_back(data: bytes, markup: str) -> None:
    assert decode_legacy(data) == markup
    assert encode_legacy(markup) == data


def test_hex_codes_may_be_lowercase() -> None:
    assert encode_legacy("{8c01}") == b"\x8c\x01"


@pytest.mark.parametrize(
    ("markup", "message"),
    [
        ("Zażółć", r"'ż' \(U\+017C\) has no code"),
        (f"{NARROW}é", "'é' cannot take an attribute"),
        ("{8C0}", "The { at 0 does not start a hex code"),
        ("{XY}", "The { at 0 does not start a hex code"),
        (f"a{OPENING}", "ends with an attribute"),
    ],
)
def test_markup_the_encoding_cannot_hold_is_refused(markup: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        encode_legacy(markup)


@pytest.mark.parametrize(
    ("data", "count"),
    [
        (b"ok\n", 0),
        (b"\x8c\x03 \x8c\x01", 3),
        (b"\x8d\x02\x8c\xff", 257),
        (b"\x80\x8c\x8d", 0),
    ],
)
def test_strings_need_the_glyphs_up_to_the_last_they_use(data: bytes, count: int) -> None:
    assert glyphs_used(data) == count
