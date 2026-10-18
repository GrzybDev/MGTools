from dataclasses import replace

import pytest

from mgtools.errors import FormatError
from mgtools.mc.gcx.nodes import Block, Call, Command, Int, ResourceRef, String, Symbol
from mgtools.mc.gcx.script import (
    GLYPH_BYTES,
    DataResource,
    Proc,
    Script,
    StringResource,
    decode_script,
    encode_script,
)

PRINT = 0x3AB23B
GLYPHS = bytes(range(GLYPH_BYTES)) + bytes(GLYPH_BYTES - 4) + bytes(4)


def script(*, bluepoint: bool, seed: int = 0) -> Script:
    def text(value: str) -> str | None:
        return value if bluepoint else None

    return Script(
        bluepoint=bluepoint,
        timestamp=0x43E6D30F,
        seed=seed,
        procs=(
            Proc(2, Block((Command(PRINT, (String(b"second"),)),))),
            Proc(1, Block((Call(2),)), language=0x10),
            Proc(3, Block(())),
        ),
        main=Block((Call(0x8001, (ResourceRef(1),)),)),
        resources=(
            StringResource(b"Save?\n", text("Save?\n")),
            DataResource((Int(1), String(b"KNIFE"), Symbol(0x06C0B43F))),
            StringResource(b"Yes", text("Sure")),
        ),
        glyphs=GLYPHS,
    )


@pytest.mark.parametrize("bluepoint", [True, False])
def test_scripts_encode_and_decode_back(bluepoint: bool) -> None:
    original = script(bluepoint=bluepoint, seed=0 if bluepoint else 0x4369EA9C)

    data = encode_script(original)

    assert data.startswith(b"LCGB") == bluepoint
    assert len(data) % (4 if bluepoint else 16) == 0
    assert decode_script(data) == original


def test_a_seed_encrypts_the_resources_and_zero_leaves_them_plain() -> None:
    assert b"Save?\n\0" in encode_script(script(bluepoint=False))
    assert b"Save?" not in encode_script(script(bluepoint=False, seed=0x4369EA9C))


def test_resources_are_padded_with_the_letters_of_font() -> None:
    plain = script(bluepoint=False)
    for legacy, padding in ((b"ab", b"F"), (b"abc", b""), (b"a", b"FO"), (b"", b"FON")):
        resources = (StringResource(legacy),)
        data = encode_script(replace(plain, resources=resources, glyphs=b""))

        assert legacy + b"\0" + padding + bytes(4) in data


def test_bluepoint_texts_follow_one_another_after_an_edit() -> None:
    original = script(bluepoint=True)
    longer = StringResource(b"Save?\n", "Zapisać grę? Tak, zapisz ją teraz.\n")
    edited = replace(original, resources=(longer, *original.resources[1:]))

    assert decode_script(encode_script(edited)) == edited


def test_bluepoint_files_need_the_last_four_glyph_bytes_blank() -> None:
    glyphs = bytes(GLYPH_BYTES - 1) + b"\x01"
    plain = replace(script(bluepoint=False), glyphs=glyphs)

    assert decode_script(encode_script(plain)).glyphs == glyphs
    with pytest.raises(ValueError, match="last 16 pixels of the last glyph blank"):
        encode_script(replace(script(bluepoint=True), glyphs=glyphs))


def with_strings(*resources: StringResource) -> Script:
    return replace(script(bluepoint=True), resources=resources)


@pytest.mark.parametrize(
    ("broken", "message"),
    [
        (
            replace(script(bluepoint=True), procs=(Proc(1, Block(())), Proc(3, Block(())))),
            "numbered from 1",
        ),
        (replace(script(bluepoint=True), seed=1), "with the seed 0"),
        (replace(script(bluepoint=True), glyphs=bytes(10)), "144 bytes each"),
        (with_strings(StringResource(b"Yes")), "resource 0 has no UTF-8 text"),
        (with_strings(StringResource(b"a\0b", "ab")), "resource 0 holds a NUL"),
        (with_strings(StringResource(b"ab", "a\0b")), "resource 0 holds a NUL"),
        (
            replace(script(bluepoint=False), resources=(StringResource(b"a", "a"),)),
            "has a UTF-8 text, but the file is plain",
        ),
    ],
)
def test_scripts_the_format_cannot_hold_are_refused(broken: Script, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        encode_script(broken)


def damaged(data: bytes, old: bytes, new: bytes) -> bytes:
    assert data.count(old) == 1
    return data.replace(old, new)


def test_malformed_files_are_reported() -> None:
    plain = encode_script(script(bluepoint=False))
    bluepoint = encode_script(script(bluepoint=True))

    with pytest.raises(FormatError, match="padded with the letters of FONT"):
        decode_script(damaged(plain, b"Yes\0F", b"Yes\0G"))
    with pytest.raises(FormatError, match="Resource 1: Unknown constant type 0x05"):
        decode_script(damaged(plain, b"\x07\x06KNIFE", b"\x05\x06KNIFE"))
    with pytest.raises(FormatError, match="Proc 2: Unknown lead byte 0x4F"):
        decode_script(damaged(plain, b"\x07\x07second", b"\x4f\x07second"))
    with pytest.raises(FormatError, match="text of resource 2 is not UTF-8"):
        decode_script(damaged(bluepoint, b"Sure\0", b"S\xffre\0"))
    with pytest.raises(FormatError, match="does not end with its padding"):
        decode_script(bluepoint + b"\1\0\0\0")
    with pytest.raises(FormatError, match="Unexpected end of data"):
        decode_script(bluepoint[:40])
