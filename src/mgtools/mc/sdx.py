"""Sound banks (pk0*.sdx): the sound effects of a stage, as SPU-ADPCM waves and MIDI.

A file holds banks back to back, then junk the engine never reads up to a
multiple of 0x800 bytes. A bank is a run of little-endian chunks, each a tag, a
u32 size and its payload: IPSQ (the size of the resident part up to TERM, the
size of the streamed BPVG chunk and the bank's sound memory slot), IWAV (per
wave: ADSR, offset with bit 31 set for BVAG, sample rate, block count and a word
of unknown meaning), IA3P, TPAT and IPAT (instrument tables), TSEQ (flags and a
record offset per sound effect id), ISEQ (the records: a 16-byte header and a
MIDI file each, padded to 4 bytes), BVAG (the resident waves), TERM and BPVG (the
streamed waves). A wave is 0x80 zero bytes followed by its SPU-ADPCM blocks.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from mgtools.binary import BinaryReader, BinaryWriter, ByteOrder
from mgtools.errors import FormatError, located
from mgtools.fileio import write_atomically, write_json
from mgtools.mc.roundtrip import import_json

_SECTOR = 0x800
_RAW_TABLES = (b"IA3P", b"TPAT", b"IPAT")
_IPSQ_SIZE = 0x38
_RESIDENT = 0x8000_0000
_WAVE_START = bytes(0x80)
_BLOCK = 16
_SOUND_IDS = 2048
_NO_SOUND = 0x00FF_FFFF
_HEADER = 16
_DOCUMENT = "sdx.json"
_PADDING = "padding.bin"


@dataclass(frozen=True, slots=True)
class Wave:
    """A wave of a bank: its IWAV entry and its SPU-ADPCM blocks."""

    sample_rate: int
    resident: bool
    """Whether the wave is in the resident BVAG chunk rather than the streamed BPVG."""
    adsr: int
    extra: int
    """The last word of the wave's IWAV entry, of unknown meaning."""
    adpcm: bytes
    """The SPU-ADPCM blocks after the zero bytes every wave starts with."""


@dataclass(frozen=True, slots=True)
class Sound:
    """A sound effect: its id, the flags of its TSEQ slot and its ISEQ record."""

    id: int
    flags: int
    header: bytes
    midi: bytes


@dataclass(frozen=True, slots=True)
class Bank:
    """A bank, without the sizes and offsets that follow from its waves and sounds."""

    slot: int
    """The sound memory slot the engine loads the bank into."""
    tables: dict[bytes, bytes]
    """The undecoded payloads of the IA3P, TPAT and IPAT chunks, by tag."""
    waves: tuple[Wave, ...]
    sounds: tuple[Sound, ...]
    """In the order of their records."""


@dataclass(frozen=True, slots=True)
class SoundBanks:
    """The banks of a pk0*.sdx file and the junk after them."""

    banks: tuple[Bank, ...]
    padding: bytes
    """The junk after the banks, cut or filled with zeros to end the last sector."""


def decode_sdx(data: bytes) -> SoundBanks:
    """Read the banks of a sound bank file and the junk that ends its last sector.

    Args:
        data: The contents of a pk0*.sdx file.
    """
    reader = BinaryReader(data)
    banks: list[Bank] = []
    while not banks or data.startswith(b"IPSQ", reader.position):
        banks.append(_read_bank(reader))
    if len(data) % _SECTOR or reader.remaining >= _SECTOR:
        msg = f"{reader.remaining} bytes follow the banks at {reader.position}"
        raise FormatError(msg)
    return SoundBanks(tuple(banks), reader.read(reader.remaining))


def encode_sdx(sound_banks: SoundBanks) -> bytes:
    """Return the .sdx file of banks, ending the last sector with their junk.

    Args:
        sound_banks: The banks to write.
    """
    data = bytearray()
    for index, bank in enumerate(sound_banks.banks):
        with located(f"Bank {index}"):
            data += _bank_bytes(bank)
    size = -len(data) % _SECTOR
    return bytes(data) + (sound_banks.padding + bytes(size))[:size]


def export_sdx(sound_banks: SoundBanks, directory: Path) -> None:
    """Write sdx.json, the padding, and per bank its tables, waves and MIDI files.

    Args:
        sound_banks: The banks to write.
        directory: The folder to write the files to.
    """
    banks = []
    for index, bank in enumerate(sound_banks.banks):
        folder = directory / f"bank{index}"
        for tag, payload in bank.tables.items():
            write_atomically(folder / f"{tag.decode()}.bin", payload)
        for number, wave in enumerate(bank.waves):
            write_atomically(folder / _wave(number), wave.adpcm)
        for sound in bank.sounds:
            write_atomically(folder / _sound(sound.id), sound.midi)
        waves = [
            {name: value for name, value in asdict(wave).items() if name != "adpcm"}
            for wave in bank.waves
        ]
        sounds = [
            {"id": sound.id, "flags": sound.flags, "header": sound.header.hex()}
            for sound in bank.sounds
        ]
        banks.append({"slot": bank.slot, "waves": waves, "sounds": sounds})
    write_atomically(directory / _PADDING, sound_banks.padding)
    write_json(directory / _DOCUMENT, {"banks": banks})


def import_sdx(directory: Path) -> SoundBanks:
    """Read banks written by export_sdx.

    Args:
        directory: The folder export_sdx wrote.
    """
    return import_json(
        directory / _DOCUMENT,
        lambda document: _sound_banks(document, directory),
        encode_sdx,
    )


def _sound_banks(document: Any, directory: Path) -> SoundBanks:
    """Return the banks of sdx.json, with the files it names in directory."""
    banks = tuple(
        _load_bank(directory / f"bank{index}", bank) for index, bank in enumerate(document["banks"])
    )
    return SoundBanks(banks, (directory / _PADDING).read_bytes())


def _wave(number: int) -> str:
    """Return the path of a wave's blocks, relative to its bank's folder."""
    return f"waves/{number:03}.adpcm"


def _sound(sound_id: int) -> str:
    """Return the path of a sound effect's MIDI file, relative to its bank's folder."""
    return f"sounds/{sound_id:04}.mid"


def _load_bank(folder: Path, bank: dict[str, Any]) -> Bank:
    tables = {tag: (folder / f"{tag.decode()}.bin").read_bytes() for tag in _RAW_TABLES}
    waves = tuple(
        Wave(**wave, adpcm=(folder / _wave(number)).read_bytes())
        for number, wave in enumerate(bank["waves"])
    )
    sounds = tuple(
        Sound(
            sound["id"],
            sound["flags"],
            bytes.fromhex(sound["header"]),
            (folder / _sound(sound["id"])).read_bytes(),
        )
        for sound in bank["sounds"]
    )
    return Bank(bank["slot"], tables, waves, sounds)


def _read_bank(reader: BinaryReader) -> Bank:
    start = reader.position
    chunks = {
        tag: _read_chunk(reader, tag)
        for tag in (b"IPSQ", b"IWAV", *_RAW_TABLES, b"TSEQ", b"ISEQ", b"BVAG")
    }
    ipsq = BinaryReader(chunks[b"IPSQ"])
    head_size, stream_size, slot = ipsq.unpack("IIh")
    if len(chunks[b"IPSQ"]) != _IPSQ_SIZE or any(ipsq.read(ipsq.remaining)):
        msg = f"The IPSQ chunk at {start} is not {_IPSQ_SIZE} bytes ending in zeros"
        raise FormatError(msg)
    if head_size != reader.position - start or _read_chunk(reader, b"TERM"):
        msg = f"The bank at {start} does not end with TERM at {head_size}"
        raise FormatError(msg)
    streamed = _read_chunk(reader, b"BPVG")
    if stream_size != 8 + len(streamed):
        msg = f"The bank at {start} gives {stream_size} as the size of its BPVG chunk"
        raise FormatError(msg)
    return Bank(
        slot,
        {tag: chunks[tag] for tag in _RAW_TABLES},
        _read_waves(chunks[b"IWAV"], chunks[b"BVAG"], streamed),
        _read_sounds(chunks[b"TSEQ"], chunks[b"ISEQ"]),
    )


def _read_chunk(reader: BinaryReader, tag: bytes) -> bytes:
    if (found := reader.read(4)) != tag:
        msg = f"Expected {tag.decode()} at {reader.position - 4}, found {found!r}"
        raise FormatError(msg)
    return reader.read(reader.u32())


def _read_waves(table: bytes, resident: bytes, streamed: bytes) -> tuple[Wave, ...]:
    """Read the waves, which each region holds back to back in table order."""
    if len(table) % 16:
        msg = f"The IWAV chunk takes {len(table)} bytes, not a multiple of 16"
        raise FormatError(msg)
    waves = []
    ends = {True: 0, False: 0}
    entries = BinaryReader(table).iter_unpack("IIHHI", len(table) // 16)
    for number, (adsr, offset, rate, blocks, extra) in enumerate(entries):
        in_resident = bool(offset & _RESIDENT)
        region = resident if in_resident else streamed
        start = offset & ~_RESIDENT
        end = start + len(_WAVE_START) + _BLOCK * blocks
        if start != ends[in_resident] or end > len(region):
            msg = f"Wave {number} is not stored right after the one before it"
            raise FormatError(msg)
        if not region.startswith(_WAVE_START, start):
            msg = f"Wave {number} does not start with {len(_WAVE_START)} zero bytes"
            raise FormatError(msg)
        adpcm = region[start + len(_WAVE_START) : end]
        waves.append(Wave(rate, in_resident, adsr, extra, adpcm))
        ends[in_resident] = end
    if ends != {True: len(resident), False: len(streamed)}:
        msg = "The waves do not fill the BVAG and BPVG chunks"
        raise FormatError(msg)
    return tuple(waves)


def _read_sounds(slots: bytes, records: bytes) -> tuple[Sound, ...]:
    """Read the sound effects, whose records follow each other in ISEQ."""
    if len(slots) != 4 * _SOUND_IDS:
        msg = f"The TSEQ chunk takes {len(slots)} bytes, not {4 * _SOUND_IDS}"
        raise FormatError(msg)
    used = [
        (sound_id, value)
        for sound_id, (value,) in enumerate(BinaryReader(slots).iter_unpack("I", _SOUND_IDS))
        if value != _NO_SOUND
    ]
    by_offset = {value & 0xFF_FFFF: (sound_id, value >> 24) for sound_id, value in used}
    if len(by_offset) != len(used):
        msg = "Several sound effects share an ISEQ record"
        raise FormatError(msg)
    bounds = [*sorted(by_offset), len(records)]
    if bounds[0]:
        msg = "The ISEQ chunk starts with bytes no sound effect uses"
        raise FormatError(msg)
    sounds = []
    for offset, end in pairwise(bounds):
        record = records[offset:end]
        if (midi_size := _midi_size(record[_HEADER:])) is None:
            msg = f"The ISEQ record at {offset} holds no MIDI file"
            raise FormatError(msg)
        midi_end = _HEADER + midi_size
        if record[midi_end:] != bytes(-midi_end % 4):
            msg = f"The ISEQ record at {offset} does not end with padding to 4 bytes"
            raise FormatError(msg)
        sound_id, flags = by_offset[offset]
        sounds.append(Sound(sound_id, flags, record[:_HEADER], record[_HEADER:midi_end]))
    return tuple(sounds)


def _midi_size(data: bytes) -> int | None:
    """Return the size of the standard MIDI file data starts with, if it does."""
    reader = BinaryReader(data, ByteOrder.BIG)
    try:
        if reader.read(4) != b"MThd":
            return None
        header = reader.read(reader.u32())
        for _ in range(int.from_bytes(header[2:4])):
            if reader.read(4) != b"MTrk":
                return None
            reader.read(reader.u32())
    except FormatError:
        return None
    return reader.position


def _bank_bytes(bank: Bank) -> bytes:
    table, resident, streamed = _wave_bytes(bank.waves)
    slots, records = _sound_bytes(bank.sounds)
    head = BinaryWriter()
    _write_chunk(head, b"IWAV", table)
    for tag in _RAW_TABLES:
        _write_chunk(head, tag, bank.tables[tag])
    _write_chunk(head, b"TSEQ", slots)
    _write_chunk(head, b"ISEQ", records)
    _write_chunk(head, b"BVAG", resident)
    ipsq = BinaryWriter()
    ipsq.pack("IIh", 8 + _IPSQ_SIZE + len(head), 8 + len(streamed), bank.slot)
    ipsq.write(bytes(_IPSQ_SIZE - len(ipsq)))
    writer = BinaryWriter()
    _write_chunk(writer, b"IPSQ", ipsq.getvalue())
    writer.write(head.getvalue())
    _write_chunk(writer, b"TERM", b"")
    _write_chunk(writer, b"BPVG", streamed)
    return writer.getvalue()


def _wave_bytes(waves: Sequence[Wave]) -> tuple[bytes, bytes, bytes]:
    """Return the IWAV table and the resident and streamed waves."""
    table = BinaryWriter()
    regions = {True: bytearray(), False: bytearray()}
    for number, wave in enumerate(waves):
        blocks, rest = divmod(len(wave.adpcm), _BLOCK)
        if rest or blocks > 0xFFFF or not 0 < wave.sample_rate <= 0xFFFF:
            msg = (
                f"Wave {number} needs up to 65535 blocks of 16 bytes and a sample "
                "rate up to 65535 Hz"
            )
            raise ValueError(msg)
        region = regions[wave.resident]
        offset = len(region) | (_RESIDENT if wave.resident else 0)
        table.pack("IIHHI", wave.adsr, offset, wave.sample_rate, blocks, wave.extra)
        region += _WAVE_START + wave.adpcm
    return table.getvalue(), bytes(regions[True]), bytes(regions[False])


def _sound_bytes(sounds: Sequence[Sound]) -> tuple[bytes, bytes]:
    """Return the TSEQ slots and the ISEQ records of the sound effects."""
    slots = [_NO_SOUND] * _SOUND_IDS
    records = bytearray()
    for sound in sounds:
        if not 0 <= sound.id < _SOUND_IDS or slots[sound.id] != _NO_SOUND:
            msg = f"Sound effect {sound.id} is repeated or past 2047"
            raise ValueError(msg)
        if not 0 <= sound.flags <= 0xFF or len(sound.header) != _HEADER:
            msg = f"Sound effect {sound.id} needs flags up to 255 and a 16-byte header"
            raise ValueError(msg)
        if _midi_size(sound.midi) != len(sound.midi):
            msg = f"Sound effect {sound.id} is not one MIDI file"
            raise ValueError(msg)
        if len(records) > 0xFF_FFFF:
            msg = "The sound effects pass the 16 MiB TSEQ reaches"
            raise ValueError(msg)
        slots[sound.id] = sound.flags << 24 | len(records)
        records += sound.header + sound.midi + bytes(-len(sound.midi) % 4)
    tseq = BinaryWriter()
    tseq.pack(f"{_SOUND_IDS}I", *slots)
    return tseq.getvalue(), bytes(records)


def _write_chunk(writer: BinaryWriter, tag: bytes, payload: bytes) -> None:
    writer.write(tag)
    writer.u32(len(payload))
    writer.write(payload)
