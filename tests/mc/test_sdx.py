import struct
from dataclasses import replace
from pathlib import Path

import pytest

from mgtools.errors import FormatError
from mgtools.mc.sdx import (
    Bank,
    Sound,
    SoundBanks,
    Wave,
    decode_sdx,
    encode_sdx,
    export_sdx,
    import_sdx,
)

MIDI = bytes.fromhex("4d546864 00000006 0000 0001 0030 4d54726b 00000004 00ff2f00")
LONGER_MIDI = bytes.fromhex("4d546864 00000006 0000 0001 0030 4d54726b 00000008 00903c40 00ff2f00")
ADSR = 0x1FC3_00FF
BANKS = SoundBanks(
    (
        Bank(
            0,
            {b"IA3P": bytes(4), b"TPAT": b"\x00\x00\x01\x3c", b"IPAT": bytes(16)},
            (
                Wave(44100, False, ADSR, 0, bytes(range(32))),
                Wave(22050, True, ADSR, 7, bytes(16)),
            ),
            (Sound(5, 0, bytes(16), MIDI), Sound(2, 8, b"\x01" * 16, LONGER_MIDI)),
        ),
        Bank(-1, {b"IA3P": b"", b"TPAT": b"", b"IPAT": b""}, (), ()),
    ),
    b"junk",
)
DATA = encode_sdx(BANKS)


def test_banks_encode_one_after_another_with_their_tables_and_decode_back() -> None:
    head_size, stream_size = struct.unpack_from("<II", DATA, 8)
    second = head_size + 8 + stream_size
    second_head, second_stream, slot = struct.unpack_from("<IIh", DATA, second + 8)
    end = second + second_head + 8 + second_stream
    sound_slots = struct.unpack_from("<6I", DATA, DATA.index(b"TSEQ") + 8)

    decoded = decode_sdx(DATA)

    assert DATA[head_size : head_size + 12] == b"TERM\0\0\0\0BPVG"
    assert (DATA[second : second + 4], slot) == (b"IPSQ", -1)
    assert len(DATA) == 0x4800
    assert DATA[end:] == b"junk" + bytes(0x4800 - end - 4)
    assert struct.unpack_from("<IIHHIIIHHI", DATA, 0x48) == (
        *(ADSR, 0, 44100, 2, 0),
        *(ADSR, 0x8000_0000, 22050, 1, 7),
    )
    assert sound_slots == (0xFF_FFFF, 0xFF_FFFF, 0x0800_002C, 0xFF_FFFF, 0xFF_FFFF, 0)
    assert decoded.banks == BANKS.banks
    assert decoded.padding.startswith(b"junk")
    assert encode_sdx(decoded) == DATA


def _patched(offset: int, patch: bytes) -> bytes:
    return DATA[:offset] + patch + DATA[offset + len(patch) :]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        pytest.param(_patched(0, b"RIFF"), "Expected IPSQ at 0, found b'RIFF'", id="tag"),
        pytest.param(DATA[:-1], "1323 bytes follow the banks at 17108", id="cut sector"),
        pytest.param(
            DATA + bytes(0x800),
            "3372 bytes follow the banks at 17108",
            id="extra sector",
        ),
        pytest.param(
            _patched(0x48 + 10, b"\x03"),
            "Wave 0 is not stored right after",
            id="wave size",
        ),
        pytest.param(
            _patched(DATA.index(b"BPVG") + 8, b"\x01"),
            "Wave 0 does not start with 128 zero bytes",
            id="wave start",
        ),
        pytest.param(
            _patched(DATA.index(b"TSEQ") + 16, bytes(4)),
            "Several sound effects share an ISEQ record",
            id="shared record",
        ),
        pytest.param(
            _patched(DATA.index(b"MThd"), b"MTrk"),
            "The ISEQ record at 0 holds no MIDI file",
            id="no midi",
        ),
    ],
)
def test_malformed_banks_are_reported(data: bytes, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        decode_sdx(data)


@pytest.mark.parametrize(
    ("bank", "message"),
    [
        (
            replace(BANKS.banks[0], waves=(Wave(44100, False, ADSR, 0, bytes(15)),)),
            "Bank 0: Wave 0 needs up to 65535 blocks of 16 bytes",
        ),
        (
            replace(BANKS.banks[0], waves=(Wave(96000, False, ADSR, 0, bytes(16)),)),
            "Bank 0: Wave 0 needs .* a sample rate up to 65535 Hz",
        ),
        (
            replace(BANKS.banks[0], sounds=(Sound(2, 0, bytes(16), MIDI),) * 2),
            "Bank 0: Sound effect 2 is repeated or past 2047",
        ),
        (
            replace(BANKS.banks[0], sounds=(Sound(2048, 0, bytes(16), MIDI),)),
            "Bank 0: Sound effect 2048 is repeated or past 2047",
        ),
        (
            replace(BANKS.banks[0], sounds=(Sound(2, 0, bytes(15), MIDI),)),
            "Bank 0: Sound effect 2 needs flags up to 255 and a 16-byte header",
        ),
        (
            replace(BANKS.banks[0], sounds=(Sound(2, 0, bytes(16), MIDI + bytes(1)),)),
            "Bank 0: Sound effect 2 is not one MIDI file",
        ),
    ],
)
def test_banks_the_tables_cannot_describe_are_refused(bank: Bank, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        encode_sdx(SoundBanks((bank,), b""))


def test_exported_banks_import_back(tmp_path: Path) -> None:
    decoded = decode_sdx(DATA)

    export_sdx(decoded, tmp_path)

    assert (tmp_path / "bank0" / "waves" / "001.adpcm").read_bytes() == bytes(16)
    assert (tmp_path / "bank0" / "sounds" / "0005.mid").read_bytes() == MIDI
    assert import_sdx(tmp_path) == decoded


def test_a_mistyped_value_of_sdx_json_is_reported_with_the_file(
    tmp_path: Path,
) -> None:
    export_sdx(decode_sdx(DATA), tmp_path)
    path = tmp_path / "sdx.json"
    path.write_text(path.read_text("utf-8").replace("44100", '"44100"'), "utf-8")

    with pytest.raises(ValueError, match=r"sdx\.json: "):
        import_sdx(tmp_path)


def test_a_replaced_sound_moves_the_records_after_it(tmp_path: Path) -> None:
    export_sdx(decode_sdx(DATA), tmp_path)
    (tmp_path / "bank0" / "sounds" / "0005.mid").write_bytes(LONGER_MIDI)

    data = encode_sdx(import_sdx(tmp_path))

    sounds = decode_sdx(data).banks[0].sounds
    assert [sound.midi for sound in sounds] == [LONGER_MIDI, LONGER_MIDI]
    assert struct.unpack_from("<I", data, data.index(b"TSEQ") + 16) == (0x0800_0030,)
