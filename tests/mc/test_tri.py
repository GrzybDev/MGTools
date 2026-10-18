import struct
from dataclasses import replace
from pathlib import Path

import pytest

from mgtools.errors import FormatError
from mgtools.fileio import read_json, write_json
from mgtools.mc.tri import (
    Atlas,
    Register,
    Sprite,
    decode_atlas,
    encode_atlas,
    export_atlas,
    import_atlas,
)

ENTRY = 0x20


def registers(mode: int = 2, **clamp: int) -> dict[str, Register]:
    page = {"TBP0": 0x1234, "TBW": 1, "PSM": 20, "TW": 6, "TH": 5, "TCC": 1}
    page |= {"TFX": 0, "CBP": 0x2E0, "CPSM": 0, "CSM": 0, "CSA": 3, "CLD": 0}
    rectangle = {"MINU": 8, "MAXU": 39, "MINV": 4, "MAXV": 11}
    return {
        "TEX1_1": {"LCM": 1, "MXL": 0, "MMAG": 1, "MMIN": 1, "MTBA": 1, "L": 0, "K": 0},
        "TEX2_1": page | {"TBP0": 0, "TW": 0, "TH": 0, "CLD": 4},
        "TEX0_1": page,
        "ALPHA_1": {"A": 0, "B": 2, "C": 1, "D": 1, "FIX": 0},
        "CLAMP_1": {"WMS": mode, "WMT": mode} | rectangle | clamp,
    }


ATLAS = Atlas(2, 1, 4, (Sprite(0x53C115, 1, registers()),))


def test_an_atlas_encodes_its_sprites_before_the_zeroed_gs_memory_and_decodes_back() -> None:
    data = encode_atlas(ATLAS)

    assert struct.unpack_from("<8I", data) == (0, 2, 2, 1, 1, 4, 0x100, 0x300)
    assert len(data) == 0x400
    assert not any(data[ENTRY + 192 :])
    assert struct.unpack_from("<3I2H", data, ENTRY + 0x10) == (0x53C115, 0, 1, 0x1234, 0x2E0)
    assert data[ENTRY + 0x40 : ENTRY + 0x50] == bytes.fromhex("0180000000000070 eeeefe0f00000000")
    clamp = 2 | 2 << 2 | 8 << 4 | 39 << 14 | 4 << 24 | 11 << 34
    assert struct.unpack_from("<2Q", data, ENTRY + 0x90) == (clamp, 0x08)
    # Pages of 64x32 texels; texels 8 to 39 across and 4 to 11 down.
    assert struct.unpack_from("<4f", data, ENTRY) == (8.5 / 64, 4.5 / 32, 31 / 64, 7 / 32)
    quad = struct.unpack_from("<8f", data, ENTRY + 0xA0)
    assert quad[0] == pytest.approx(-31 / 64 * 0.4999)
    assert quad[1] == pytest.approx(-7 / 32 * 0.4999)
    assert quad[2:] == (1, 1, 0.375, 0.25, 0, 0)
    assert decode_atlas(data) == ATLAS


def test_a_repeated_sprite_covers_its_whole_page() -> None:
    data = encode_atlas(replace(ATLAS, sprites=(Sprite(1, 0, registers(mode=1)),)))

    assert struct.unpack_from("<4f", data, ENTRY) == (0, 0, 1, 1)
    assert struct.unpack_from("<8f", data, ENTRY + 0xA0)[4:6] == (0.5, 0.5)


@pytest.mark.parametrize(
    ("clamp", "message"),
    [
        ({"MAXU": 1024}, "Sprite 0: CLAMP_1 MAXU takes 10 bits, not 1024"),
        ({"MAXU": 64}, "Sprite 0: CLAMP_1 MINU 8 and MAXU 64 must be in order within "),
        ({"MINV": 12}, "MINV 12 and MAXV 11 must be in order within its page, 32 "),
    ],
)
def test_rectangles_outside_their_page_or_register_are_refused(
    clamp: dict[str, int], message: str
) -> None:
    atlas = replace(ATLAS, sprites=(Sprite(1, 0, registers(**clamp)),))

    with pytest.raises(ValueError, match=message):
        encode_atlas(atlas)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (encode_atlas(ATLAS)[:-1], "Not a sprite atlas: its header gives another size"),
        (
            encode_atlas(ATLAS)[:0x300] + b"\x01" + bytes(255),
            "cannot keep, at offset 0x300",
        ),
    ],
)
def test_files_that_are_no_atlas_or_hold_texel_data_are_refused(data: bytes, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        decode_atlas(data)


def test_a_rectangle_edited_in_json_moves_the_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "atlas.json"
    export_atlas(ATLAS, path)
    assert import_atlas(path) == ATLAS
    document = read_json(path)
    assert document["sprites"][0]["code"] == "0053c115"

    document["sprites"][0]["CLAMP_1"]["MAXU"] = 63
    write_json(path, document)

    data = encode_atlas(import_atlas(path))
    assert struct.unpack_from("<f", data, ENTRY + 8) == (55 / 64,)


def test_a_mistyped_value_in_the_json_is_reported_with_the_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "atlas.json"
    export_atlas(ATLAS, path)
    document = read_json(path)
    document["sprites"][0]["CLAMP_1"]["MAXU"] = "39"
    write_json(path, document)

    with pytest.raises(ValueError, match=r"atlas\.json: Sprite 0: .* not '39'"):
        import_atlas(path)
