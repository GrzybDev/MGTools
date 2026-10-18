"""GCX files: the compiled scripts of the Master Collection's stages.

A file holds a timestamp; a table of procs, each the language it is for in the
high byte above the offset of its body, ended by FFFFFFFF; then, from the end of
that table, the offsets of the code, of the resource table, of the resources and
of the glyphs, and the seed of the cipher over the resources. Resources are
strings in the PS2 text encoding or lists of values, padded to 4 bytes with the
letters of "FONT". The glyphs are those the PS2 encoding lacks, 24 by 24 pixels
of 2 bits. The code is the bodies of the procs, then main. Plain files are padded
to 16 bytes. Bluepoint files, which the game prefers, start with LCGB, leave the
resources unencrypted, add each string's text in UTF-8, give the glyphs a size
that drops their last 4 bytes, and are padded to 4 bytes.
"""

from dataclasses import dataclass, replace

from mgtools.binary import BinaryReader, BinaryWriter
from mgtools.errors import FormatError, located
from mgtools.mc.gcx.bytecode import encode_node, read_block, read_values
from mgtools.mc.gcx.nodes import Block, Value

_MAGIC = b"LCGB"
GLYPH_SIZE = 24
GLYPH_BYTES = GLYPH_SIZE * GLYPH_SIZE // 4

_END_OF_TABLE = 0xFFFF_FFFF
_NO_TEXT = 0xFFFF_FFFF
_OFFSET_MASK = 0xFF_FFFF
_STRING = 0x80
_DATA = 0x00
_PADDING = b"FONT"
_PLAIN_HEADER = 0x14
_BLUEPOINT_HEADER = 0x18


@dataclass(frozen=True, slots=True)
class Proc:
    """A proc, its number, body and language: the language id times 16, or 0 for all."""

    id: int
    body: Block
    language: int = 0


@dataclass(frozen=True, slots=True)
class StringResource:
    """A string in the PS2 encoding, with the UTF-8 text Bluepoint files show."""

    legacy: bytes
    text: str | None = None


@dataclass(frozen=True, slots=True)
class DataResource:
    """A list of values, such as a row of the item table."""

    values: tuple[Value, ...]


type Resource = StringResource | DataResource


@dataclass(frozen=True, slots=True)
class Script:
    """A GCX file, with its procs in the order their bodies are stored."""

    bluepoint: bool
    timestamp: int
    seed: int
    procs: tuple[Proc, ...]
    main: Block
    resources: tuple[Resource, ...]
    glyphs: bytes


def decode_script(data: bytes) -> Script:
    """Read a GCX file, plain or Bluepoint, decrypting its resources.

    Args:
        data: The contents of a .gcx file.
    """
    bluepoint = data.startswith(_MAGIC)
    reader = BinaryReader(data)
    reader.read(len(_MAGIC) if bluepoint else 0)
    timestamp = reader.u32()
    table = list(iter(reader.u32, _END_OF_TABLE))
    base = reader.position
    code_at, table_at, area_at, glyphs_at, seed = reader.unpack("5I")
    header_size = _BLUEPOINT_HEADER if bluepoint else _PLAIN_HEADER
    if bluepoint and (reader.u32() != _BLUEPOINT_HEADER or seed):
        msg = "The header of the Bluepoint file is unknown"
        raise FormatError(msg)
    size = len(data) - base
    if not header_size <= table_at <= area_at <= glyphs_at <= code_at <= size:
        msg = "The sections of the file are out of order"
        raise FormatError(msg)
    count, rest = divmod(area_at - table_at, 4)
    if rest or (not bluepoint and table_at != header_size):
        msg = "The resource table does not follow the header or holds part of an entry"
        raise FormatError(msg)

    def section(start: int, end: int) -> BinaryReader:
        return BinaryReader(data[base + start : base + end])

    entries = section(table_at, area_at).unpack(f"{count}I")
    area = _cipher(data[base + area_at : base + glyphs_at], seed)
    resources = _decode_resources(entries, area)
    if bluepoint:
        texts = _decode_texts(section(header_size, table_at), count)
        resources = _with_texts(resources, texts)
    glyphs = _decode_glyphs(section(glyphs_at, code_at), bluepoint)
    procs, main = _decode_code(table, data, base + code_at, 4 if bluepoint else 16)
    return Script(bluepoint, timestamp, seed, procs, main, tuple(resources), glyphs)


def encode_script(script: Script) -> bytes:
    """Return the GCX file of a script, with the offsets that follow from it.

    Args:
        script: The script to write.
    """
    _check(script)
    bodies = BinaryWriter()
    offsets = {}
    for proc in script.procs:
        offsets[proc.id] = len(bodies)
        bodies.write(encode_node(proc.body))
    main = encode_node(script.main)
    entries, area = _encode_resources(script.resources)
    glyphs = len(script.glyphs).to_bytes(4, "little") + script.glyphs
    texts = b""
    if script.bluepoint:
        texts = _encode_texts(script.resources)
        # The Bluepoint converter put a size before the glyphs without making room.
        if glyphs[-4:] != bytes(4):
            msg = "Bluepoint files need the last 16 pixels of the last glyph blank"
            raise ValueError(msg)
        glyphs = len(glyphs).to_bytes(4, "little") + glyphs[:-4]
    table_at = _PLAIN_HEADER + len(texts)
    area_at = table_at + 4 * len(entries)
    glyphs_at = area_at + len(area)
    code_at = glyphs_at + len(glyphs)

    writer = BinaryWriter()
    writer.write(_MAGIC if script.bluepoint else b"")
    writer.u32(script.timestamp)
    for proc in sorted(script.procs, key=lambda proc: proc.id):
        writer.u32(_entry(proc.language, offsets[proc.id]))
    writer.u32(_END_OF_TABLE)
    writer.pack("5I", code_at, table_at, area_at, glyphs_at, script.seed)
    writer.write(texts)
    writer.pack(f"{len(entries)}I", *entries)
    writer.write(_cipher(area, script.seed))
    writer.write(glyphs)
    for code in (bodies.getvalue(), main):
        writer.u32(len(code))
        writer.write(code)
    writer.write(bytes(-len(writer) % (4 if script.bluepoint else 16)))
    return writer.getvalue()


def _cipher(data: bytes, seed: int) -> bytes:
    """Encrypt or decrypt the resources; a zero seed leaves them as they are."""
    if not seed:
        return data
    result = bytearray(data)
    state = seed
    for index in range(len(result)):
        state = (state * 0x7D2B89DD + 0xCF9) & 0xFFFF_FFFF
        result[index] ^= state >> 15 & 0xFF
    return bytes(result)


def _decode_resources(entries: tuple[int, ...], area: bytes) -> list[Resource]:
    reader = BinaryReader(area)
    resources: list[Resource] = []
    for index, entry in enumerate(entries):
        if entry & _OFFSET_MASK != reader.position:
            msg = f"Resource {index} does not start where the previous one ends"
            raise FormatError(msg)
        with located(f"Resource {index}"):
            kind = entry >> 24
            if kind == _STRING:
                resources.append(StringResource(bytes(iter(reader.u8, 0))))
            elif kind == _DATA:
                resources.append(DataResource(read_values(reader)))
            else:
                msg = f"Unknown kind 0x{kind:02X}"
                raise FormatError(msg)
    end = reader.position
    if reader.read(reader.remaining) != _PADDING[: -end % 4]:
        msg = "The resources are not padded with the letters of FONT"
        raise FormatError(msg)
    return resources


def _decode_texts(reader: BinaryReader, count: int) -> list[str | None]:
    if reader.u32() != count:
        msg = "The UTF-8 texts are not one per resource"
        raise FormatError(msg)
    texts: list[str | None] = []
    for index, offset in enumerate(reader.unpack(f"{count}I")):
        if offset == _NO_TEXT:
            texts.append(None)
            continue
        if offset != reader.position:
            msg = f"The UTF-8 text of resource {index} does not follow the one before"
            raise FormatError(msg)
        try:
            texts.append(bytes(iter(reader.u8, 0)).decode())
        except UnicodeDecodeError as error:
            msg = f"The text of resource {index} is not UTF-8: {error}"
            raise FormatError(msg) from error
    if reader.remaining:
        msg = "The UTF-8 texts are followed by unknown bytes"
        raise FormatError(msg)
    return texts


def _with_texts(resources: list[Resource], texts: list[str | None]) -> list[Resource]:
    """Return the resources with their UTF-8 texts, which strings need and data lacks."""
    merged: list[Resource] = []
    for index, (resource, text) in enumerate(zip(resources, texts, strict=True)):
        match resource, text:
            case StringResource(), str():
                merged.append(replace(resource, text=text))
            case DataResource(), None:
                merged.append(resource)
            case _:
                msg = f"Resource {index} is a string without UTF-8 text or data with it"
                raise FormatError(msg)
    return merged


def _decode_glyphs(reader: BinaryReader, bluepoint: bool) -> bytes:
    if bluepoint:
        if reader.u32() != reader.remaining + 4:
            msg = "The glyphs of the Bluepoint file do not start with their size"
            raise FormatError(msg)
        reader = BinaryReader(reader.read(reader.remaining) + bytes(4))
    size = reader.u32()
    if size != reader.remaining or size % GLYPH_BYTES:
        msg = f"The glyphs take {reader.remaining} bytes, not {size} as whole glyphs"
        raise FormatError(msg)
    return reader.read(size)


def _decode_code(
    table: list[int], data: bytes, start: int, alignment: int
) -> tuple[tuple[Proc, ...], Block]:
    """Read the procs the table locates and main from the code at start."""
    reader = BinaryReader(data[start:])
    bodies = BinaryReader(reader.read(reader.u32()))
    procs = []
    for number in sorted(range(len(table)), key=lambda n: table[n] & _OFFSET_MASK):
        if table[number] & _OFFSET_MASK != bodies.position:
            msg = f"Proc {number + 1} does not start where the body before it ends"
            raise FormatError(msg)
        with located(f"Proc {number + 1}"):
            procs.append(Proc(number + 1, read_block(bodies), table[number] >> 24))
    code = BinaryReader(reader.read(reader.u32()))
    with located("Main"):
        main = read_block(code)
    if bodies.remaining or code.remaining:
        msg = "The code holds unknown bytes after the procs or main"
        raise FormatError(msg)
    end = len(data) - reader.remaining
    if reader.read(reader.remaining) != bytes(-end % alignment):
        msg = "The file does not end with its padding after the code"
        raise FormatError(msg)
    return tuple(procs), main


def _check(script: Script) -> None:
    """Refuse a script that its variant of the file cannot hold."""
    numbers = sorted(proc.id for proc in script.procs)
    if numbers != list(range(1, len(numbers) + 1)):
        msg = "The procs must be numbered from 1 up, each once"
        raise ValueError(msg)
    if script.bluepoint and script.seed:
        msg = "Bluepoint files leave their resources unencrypted, with the seed 0"
        raise ValueError(msg)
    if len(script.glyphs) % GLYPH_BYTES:
        msg = f"Glyphs take {GLYPH_BYTES} bytes each, not {len(script.glyphs)} in all"
        raise ValueError(msg)
    for index, resource in enumerate(script.resources):
        match resource:
            case StringResource(text=None) if script.bluepoint:
                msg = f"String resource {index} has no UTF-8 text"
                raise ValueError(msg)
            case StringResource(text=str()) if not script.bluepoint:
                msg = f"String resource {index} has a UTF-8 text, but the file is plain"
                raise ValueError(msg)


def _encode_resources(resources: tuple[Resource, ...]) -> tuple[list[int], bytes]:
    """Return the entries of the resource table and the unencrypted resources."""
    area = bytearray()
    entries = []
    for index, resource in enumerate(resources):
        match resource:
            case StringResource(legacy):
                entries.append(_entry(_STRING, len(area)))
                area += _terminated(legacy, f"String resource {index}")
            case DataResource(values):
                entries.append(_entry(_DATA, len(area)))
                area += b"".join(encode_node(value) for value in values) + b"\0"
    area += _PADDING[: -len(area) % 4]
    return entries, bytes(area)


def _encode_texts(resources: tuple[Resource, ...]) -> bytes:
    """Return the end of the header of a Bluepoint file and its UTF-8 texts."""
    section = BinaryWriter()
    section.pack("2I", _BLUEPOINT_HEADER, len(resources))
    pool = bytearray()
    start = 4 + 4 * len(resources)
    for index, resource in enumerate(resources):
        if isinstance(resource, StringResource) and resource.text is not None:
            section.u32(start + len(pool))
            text = resource.text.encode()
            pool += _terminated(text, f"The text of resource {index}")
        else:
            section.u32(_NO_TEXT)
    section.write(pool)
    return section.getvalue()


def _entry(high: int, offset: int) -> int:
    """Return a table entry: high in the top byte, above a 24-bit offset."""
    if offset > _OFFSET_MASK:
        msg = "The procs and the resources take 16 MiB at most each"
        raise ValueError(msg)
    return high << 24 | offset


def _terminated(data: bytes, what: str) -> bytes:
    """Return data with a NUL after it, refusing data that holds one; what names it."""
    if b"\0" in data:
        msg = f"{what} holds a NUL character"
        raise ValueError(msg)
    return data + b"\0"
