from dataclasses import dataclass, field


@dataclass
class GclEnd:
    """Bytecode 0x00 – end marker"""

    pass


@dataclass
class GclShort:
    """Bytecode 0x01 – signed 16-bit value"""

    value: int


@dataclass
class GclByte:
    """Bytecodes 0x02/0x03/0x04 – unsigned 8-bit value"""

    code: int  # 2, 3, or 4 — preserved for round-trip
    value: int


@dataclass
class GclStrCode:
    """Bytecodes 0x06/0x08 – 24-bit strcode hash"""

    code: int  # 6 or 8
    value: int
    resolved: str | None = None  # if we resolved it from a dictionary


@dataclass
class GclString:
    """Bytecode 0x07 – inline string (EUC-JP / ASCII)"""

    data: bytes  # raw bytes including NUL terminator


@dataclass
class GclLong:
    """Bytecodes 0x09/0x0A – 32-bit integer value"""

    code: int  # 9 or 0xA
    value: int


@dataclass
class GclArray:
    """Bytecode 0x0D – strcode[index] (3-byte hash + 1-byte index)"""

    hash_value: int
    index: int
    resolved: str | None = None


@dataclass
class GclStrRes:
    """Bytecode 0x0E – string resource reference"""

    index: int


@dataclass
class GclNum:
    """Tag 0xC0 – small number encoded in single byte: (code & 0x3F) - 1"""

    value: int
    raw_code: int  # original byte for exact round-trip


@dataclass
class GclLocal:
    """Tag 0x90 – local variable reference"""

    index: int
    raw_code: int


@dataclass
class GclArg:
    """Tag 0x40 – argument reference"""

    index: int


@dataclass
class GclVar:
    """Tag 0x10 – global variable reference"""

    varcode: int  # the full 32-bit BE value (first byte is tag)


@dataclass
class GclVarArray:
    """Tag 0x20 – global variable array reference"""

    varcode: int
    max_val: object  # GCL node
    offset_val: object  # GCL node


@dataclass
class GclExpr:
    """Tag 0x30 – expression block"""

    data: bytes  # raw bytecode for the expression
    # Decoded representation:
    elements: list = field(default_factory=list)


@dataclass
class GclParam:
    """Tag 0x50 – parameter (letter + body)"""

    letter: int  # the parameter type letter (e.g. ord('c'), ord('d'), etc.)
    body: list  # list of GCL nodes inside this param


@dataclass
class GclCommand:
    """Tag 0x60 – command invocation"""

    command_hash: int
    resolved: str | None
    short_size_raw: bytes  # raw bytes that encode the short size (for round-trip)
    args: list  # GCL nodes for command arguments
    body: list  # GCL nodes for the command body (params etc.)


@dataclass
class GclCall:
    """Tag 0x70 – proc call"""

    proc_index: int  # u16 proc index into proc table
    args: list  # GCL nodes for call arguments
    data: bytes  # raw body bytes for round-trip


@dataclass
class GclProc:
    """Tag 0x80 – inline proc block"""

    body: list  # GCL nodes


@dataclass
class GclProcDef:
    """Top-level proc definition (from the proc table)"""

    index: int
    offset: int
    body: list  # GCL nodes
    raw_size_bytes: bytes  # the size encoding bytes for round-trip


@dataclass
class GclMainDef:
    """Top-level main body definition"""

    body: list
    raw_size_bytes: bytes


@dataclass
class GcxFile:
    """Complete parsed GCX file."""

    has_lcgb_header: bool
    timestamp: int
    proc_offsets: list[int]  # raw proc table entries
    # Block header
    proc_offset: int  # offset to script proc body within block
    resource_table_offset: int
    string_resources_offset: int
    font_data_offset: int
    seed: int  # encryption seed (0 = not encrypted)
    # Resource table entries (raw u32 values)
    resource_entries: list[int]
    # Raw data sections
    extra_data: bytes  # data between block header and resource table (blueprint)
    string_data: bytes  # decrypted string/resource data
    font_data: bytes
    # Script
    proc_body_data: bytes  # raw proc body bytecode
    main_body_data: bytes  # raw main body bytecode
    trailing_data: bytes  # trailing padding after main body
    # Decompiled
    procs: list[GclProcDef] = field(default_factory=list)
    main: GclMainDef | None = None
