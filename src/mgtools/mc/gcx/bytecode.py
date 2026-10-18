"""GCL bytecode: how compiled scripts encode their values and statements.

A value starts with a lead byte. From 0xC0 the lead byte is a small integer;
below, its high nibble is a tag: 0 a constant whose type is the low nibble, 1 a
variable, 2 an array element, 3 an expression, 4 an argument, 5 an option, 6 a
command, 7 a call and 8 a block. Expressions, options, commands, calls and
blocks are sized: a low nibble up to 12 is the size of the rest, 13 to 15 put it
in the next 1 to 3 bytes. Commands, calls and blocks end with a zero byte.
Expressions are in reverse Polish notation and end with the operator 0. The
compiler always chose the shortest form of numbers and sizes, so only that form
is read and written.
"""

from contextlib import suppress

from mgtools.binary import BinaryReader
from mgtools.errors import FormatError
from mgtools.mc.gcx.nodes import (
    Argument,
    Binary,
    Block,
    Call,
    Command,
    Element,
    Expression,
    Int,
    Node,
    Operand,
    Operator,
    Option,
    ProcRef,
    Region,
    ResourceRef,
    Statement,
    StrCode,
    String,
    Symbol,
    Unary,
    Value,
    Variable,
    VariableType,
)

# The operators that ignore their first operand, which the compiler made a 0.
_UNARY_OPERATORS = frozenset({Operator.NEGATE, Operator.NOT, Operator.INVERT})
_END = 0
_END_OF_EXPRESSION = 0xA0
_OPERATOR_MASK = 0xE0
_SIZED_TAGS = frozenset({3, 5, 6, 7, 8})
_LONG_ARGS = 0x80
# Integer forms from the shortest, after the small integers from -1 to 62.
_INT_FORMS = {0x02: (1, False), 0x01: (2, True), 0x09: (4, True)}


def read_block(reader: BinaryReader) -> Block:
    """Read the block at the reader's position, such as the body of a proc.

    Args:
        reader: The code, at the lead byte of the block.
    """
    block = _read(reader, reader.u8())
    if not isinstance(block, Block):
        msg = f"Expected a block before offset {reader.position}"
        raise FormatError(msg)
    return block


def read_values(reader: BinaryReader) -> tuple[Value, ...]:
    """Read values up to the zero byte that ends them, as in a data resource or a call.

    Args:
        reader: The bytecode, at the lead byte of the first value.
    """
    return tuple(_value(reader, lead) for lead in iter(reader.u8, _END))


def encode_node(node: Node) -> bytes:
    """Return the bytecode of a value, statement or option, in its shortest form.

    Args:
        node: The node to encode.
    """
    match node:
        case Int(value):
            return _encode_int(value)
        case Symbol(value):
            return b"\x0a" + value.to_bytes(4, "little")
        case StrCode(code):
            return b"\x06" + code.to_bytes(3, "little")
        case String(data):
            return bytes([0x07, len(data) + 1]) + data + b"\0"
        case ProcRef(proc):
            return b"\x08" + proc.to_bytes(2, "little")
        case ResourceRef(index):
            return b"\x0e" + index.to_bytes(2, "little")
        case Argument(index):
            return bytes([0x40 | index])
        case Variable():
            return _encode_variable(0x10, node)
        case Element(variable, size, index):
            return _encode_variable(0x20, variable) + _join((size, index))
        case Expression(root):
            return _sized(0x30, _encode_operand(root) + bytes([_END_OF_EXPRESSION]))
        case Option(letter, values):
            return _sized(0x50, letter.encode("ascii") + _join(values))
        case Command(code, args, options):
            body = code.to_bytes(3, "little") + _encode_args(args) + _join(options)
            return _sized(0x60, body + b"\0")
        case Call(proc, args):
            return _sized(0x70, proc.to_bytes(2, "little") + _join(args) + b"\0")
        case Block(statements):
            return _sized(0x80, _join(statements) + b"\0")


def _read(reader: BinaryReader, lead: int) -> Node:
    """Read the node that starts with lead, the byte just read."""
    if lead >= 0xC0:
        return Int((lead & 0x3F) - 1)
    start = reader.position - 1
    tag = lead >> 4
    if tag == 0:
        return _read_constant(reader, lead)
    if tag == 1:
        return _read_variable(reader, lead)
    if tag == 2:
        variable = _read_variable(reader, lead)
        size = _value(reader, reader.u8())
        return Element(variable, size, _value(reader, reader.u8()))
    if tag == 4 and lead != 0x4F:
        return Argument(lead & 0xF)
    if tag not in _SIZED_TAGS:
        msg = f"Unknown lead byte 0x{lead:02X} at offset {start}"
        raise FormatError(msg)
    end = _read_size(reader, lead) + reader.position
    node: Node
    match tag:
        case 3:
            node = _read_expression(reader)
        case 5:
            node = Option(_read_letter(reader), _read_values_until(reader, end))
        case 6:
            node = _read_command(reader)
        case 7:
            node = Call(reader.u16(), read_values(reader))
        case _:
            statements = (_statement(reader, first) for first in iter(reader.u8, _END))
            node = Block(tuple(statements))
    if reader.position != end:
        msg = f"What starts at offset {start} does not end where its size says"
        raise FormatError(msg)
    return node


def _value(reader: BinaryReader, lead: int) -> Value:
    """Read the node that starts with lead, refusing a statement or an option."""
    node = _read(reader, lead)
    if isinstance(node, Command | Call | Option):
        msg = f"Expected a value before offset {reader.position}, found a statement"
        raise FormatError(msg)
    return node


def _statement(reader: BinaryReader, lead: int) -> Statement:
    """Read the node that starts with lead, refusing anything but a statement."""
    node = _read(reader, lead)
    if not isinstance(node, Command | Call | Expression):
        msg = f"Expected a statement before offset {reader.position}, found a value"
        raise FormatError(msg)
    return node


def _read_constant(reader: BinaryReader, lead: int) -> Value:
    if lead in _INT_FORMS:
        size, signed = _INT_FORMS[lead]
        value = int.from_bytes(reader.read(size), "little", signed=signed)
        if _encode_int(value)[0] != lead:
            msg = f"The integer {value} before offset {reader.position} is too long"
            raise FormatError(msg)
        return Int(value)
    match lead:
        case 0x06:
            return StrCode(reader.u24())
        case 0x07:
            data = reader.read(reader.u8())
            if not data.endswith(b"\0") or b"\0" in data[:-1]:
                msg = f"The string before offset {reader.position} is malformed"
                raise FormatError(msg)
            return String(data[:-1])
        case 0x08:
            return ProcRef(reader.u16())
        case 0x0A:
            return Symbol(reader.u32())
        case 0x0E:
            return ResourceRef(reader.u16())
    msg = f"Unknown constant type 0x{lead:02X} at offset {reader.position - 1}"
    raise FormatError(msg)


def _read_variable(reader: BinaryReader, lead: int) -> Variable:
    place = reader.u8()
    offset = int.from_bytes(reader.read(2), "big")
    try:
        kind, region = VariableType(lead & 0xF), Region(place >> 4)
    except ValueError:
        msg = f"Unknown variable type or region before offset {reader.position}"
        raise FormatError(msg) from None
    if place & 0xF and kind is not VariableType.FLAG:
        msg = f"The variable before offset {reader.position} has a bit but no flag"
        raise FormatError(msg)
    return Variable(kind, region, offset, place & 0xF)


def _read_size(reader: BinaryReader, lead: int) -> int:
    nibble = lead & 0xF
    width = max(nibble - 12, 0)
    size = int.from_bytes(reader.read(width), "little") if width else nibble
    if _size_width(size) != width:
        msg = f"The size {size} before offset {reader.position} is too long"
        raise FormatError(msg)
    return size


def _read_expression(reader: BinaryReader) -> Expression:
    stack: list[Operand] = []
    while (lead := reader.u8()) != _END_OF_EXPRESSION:
        where = f"offset {reader.position - 1}"
        if lead & _OPERATOR_MASK != _END_OF_EXPRESSION:
            operand = _value(reader, lead)
            if isinstance(operand, Expression):
                msg = f"An expression holds another as an operand at {where}"
                raise FormatError(msg)
            stack.append(operand)
            continue
        try:
            operator = Operator(lead & 0x1F)
        except ValueError:
            msg = f"Unknown operator 0x{lead:02X} at {where}"
            raise FormatError(msg) from None
        if len(stack) < 2:
            msg = f"The operator at {where} lacks operands"
            raise FormatError(msg)
        right, left = stack.pop(), stack.pop()
        if operator not in _UNARY_OPERATORS:
            stack.append(Binary(operator, left, right))
        elif left == Int(0):
            stack.append(Unary(operator, right))
        else:
            msg = f"The unary operator at {where} has a first operand other than 0"
            raise FormatError(msg)
    if len(stack) != 1:
        msg = f"The expression before offset {reader.position} leaves {len(stack)} values"
        raise FormatError(msg)
    return Expression(stack[0])


def _read_letter(reader: BinaryReader) -> str:
    letter = chr(reader.u8())
    if not (letter.isascii() and letter.isalpha()):
        msg = f"The option at offset {reader.position - 1} is not a letter"
        raise FormatError(msg)
    return letter


def _read_command(reader: BinaryReader) -> Command:
    code = reader.u24()
    size = reader.u8()
    if size & _LONG_ARGS:
        size = (size & 0x7F) << 8 | reader.u8()
        if size < _LONG_ARGS:
            msg = f"The size of arguments before offset {reader.position} is too long"
            raise FormatError(msg)
    args = _read_values_until(reader, reader.position + size)
    options = []
    for lead in iter(reader.u8, _END):
        option = _read(reader, lead)
        if not isinstance(option, Option):
            msg = f"Expected an option before offset {reader.position}"
            raise FormatError(msg)
        options.append(option)
    return Command(code, args, tuple(options))


def _read_values_until(reader: BinaryReader, end: int) -> tuple[Value, ...]:
    values = []
    while reader.position < end:
        values.append(_value(reader, reader.u8()))
    if reader.position != end:
        msg = f"A value runs past offset {end}, where its list ends"
        raise FormatError(msg)
    return tuple(values)


def _encode_int(value: int) -> bytes:
    if -1 <= value <= 62:
        return bytes([0xC1 + value])
    for lead, (size, signed) in _INT_FORMS.items():
        with suppress(OverflowError):
            return bytes([lead]) + value.to_bytes(size, "little", signed=signed)
    msg = f"{value} does not fit in 32 bits"
    raise ValueError(msg)


def _encode_variable(tag: int, variable: Variable) -> bytes:
    place = variable.region << 4 | variable.bit
    return bytes([tag | variable.type, place]) + variable.offset.to_bytes(2, "big")


def _encode_operand(operand: Operand) -> bytes:
    match operand:
        case Unary(operator, value):
            operands = _encode_int(0) + _encode_operand(value)
        case Binary(operator, left, right):
            operands = _encode_operand(left) + _encode_operand(right)
        case _:
            return encode_node(operand)
    return operands + bytes([_END_OF_EXPRESSION | operator])


def _encode_args(args: tuple[Value, ...]) -> bytes:
    data = _join(args)
    if len(data) < _LONG_ARGS:
        return bytes([len(data)]) + data
    if len(data) > 0x7FFF:
        msg = f"The arguments of a command take 32767 bytes at most, not {len(data)}"
        raise ValueError(msg)
    return (_LONG_ARGS << 8 | len(data)).to_bytes(2, "big") + data


def _sized(tag: int, body: bytes) -> bytes:
    """Return a sized node: its lead byte of tag, the size of body if needed, and body."""
    width = _size_width(len(body))
    if width > 3:
        msg = f"A block or a statement takes 16 MiB at most, not {len(body)} bytes"
        raise ValueError(msg)
    if not width:
        return bytes([tag | len(body)]) + body
    return bytes([tag | 12 + width]) + len(body).to_bytes(width, "little") + body


def _size_width(size: int) -> int:
    """Return the number of bytes after a lead byte that give a size."""
    return 0 if size <= 12 else (size.bit_length() + 7) // 8


def _join(nodes: tuple[Node, ...]) -> bytes:
    """Return the bytecode of nodes back to back."""
    return b"".join(encode_node(node) for node in nodes)
