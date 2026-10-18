import pytest

from mgtools.binary import BinaryReader
from mgtools.errors import FormatError
from mgtools.mc.gcx.bytecode import encode_node, read_block, read_values
from mgtools.mc.gcx.nodes import (
    Argument,
    Binary,
    Block,
    Call,
    Command,
    Element,
    Expression,
    Int,
    Operator,
    Option,
    ProcRef,
    Region,
    ResourceRef,
    StrCode,
    String,
    Symbol,
    Unary,
    Value,
    Variable,
    VariableType,
)

COUNTER = Variable(VariableType.INT, Region.GLOBAL, 0x0010)


def decode_value(data: bytes) -> Value:
    (value,) = read_values(BinaryReader(data + b"\0"))
    return value


@pytest.mark.parametrize(
    ("data", "value"),
    [
        ("c0", Int(-1)),
        ("ff", Int(62)),
        ("02 3f", Int(63)),
        ("02 ff", Int(255)),
        ("01 00 01", Int(256)),
        ("01 fe ff", Int(-2)),
        ("01 00 80", Int(-32768)),
        ("09 00 80 00 00", Int(32768)),
        ("09 00 00 00 80", Int(-(1 << 31))),
        ("0a 33 d1 30 0d", Symbol(0x0D30D133)),
        ("06 20 07 18", StrCode(0x180720)),
        ("07 03 6f 6b 00", String(b"ok")),
        ("08 14 80", ProcRef(0x8014)),
        ("0e 2c 01", ResourceRef(300)),
        ("42", Argument(2)),
        ("19 00 00 10", COUNTER),
        ("14 07 0d d2", Variable(VariableType.FLAG, Region.GLOBAL, 0x0DD2, 7)),
        ("11 80 01 56", Variable(VariableType.SHORT, Region.LINK, 0x0156)),
        (
            "29 80 01 56 02 83 c4",
            Element(Variable(VariableType.INT, Region.LINK, 0x0156), Int(131), Int(3)),
        ),
        (
            "37 19 00 00 10 c6 b6 a0",
            Expression(Binary(Operator.ASSIGN, COUNTER, Int(5))),
        ),
        ("37 c1 19 00 00 10 a2 a0", Expression(Unary(Operator.NOT, COUNTER))),
        ("81 00", Block(())),
    ],
)
def test_values_decode_and_encode_in_their_shortest_form(data: str, value: Value) -> None:
    assert decode_value(bytes.fromhex(data)) == value
    assert encode_node(value) == bytes.fromhex(data)


def test_statements_and_options_round_trip_in_a_block() -> None:
    block = Block(
        (
            Command(0x000D86, (Expression(COUNTER),), (Option("e", (Block(()),)),)),
            Call(3, (Int(1), StrCode(0x123456))),
            Expression(Binary(Operator.ASSIGN, COUNTER, Block((Call(1),)))),
        )
    )
    data = encode_node(block)

    assert data.startswith(b"\x8d")
    assert read_block(BinaryReader(data)) == block


@pytest.mark.parametrize(
    ("length", "header"),
    [(8, "3c"), (9, "3d 0d"), (251, "3d ff"), (252, "3e 00 01")],
)
def test_sizes_take_the_nibble_or_as_few_bytes_as_they_need(length: int, header: str) -> None:
    expression = Expression(String(b"a" * length))

    data = encode_node(expression)

    assert data.startswith(bytes.fromhex(header))
    assert decode_value(data) == expression


def test_arguments_from_128_bytes_take_a_second_size_byte() -> None:
    command = Command(0x37C884, (String(b"a" * 125),))

    data = encode_node(command)

    assert data[5:7] == b"\x80\x80"
    assert read_block(BinaryReader(encode_node(Block((command,))))) == Block((command,))


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("02 05", "integer 5 .* too long"),
        ("01 10 00", "integer 16 .* too long"),
        ("3d 0b c1 a0" + " 00" * 9, "size 11 .* too long"),
        ("05", "Unknown constant type 0x05"),
        ("4f 00", "Unknown lead byte 0x4F"),
        ("07 02 61 62", "string .* malformed"),
        ("19 20 00 00", "Unknown variable type or region"),
        ("19 01 00 00", "has a bit but no flag"),
        ("34 c1 c1 b7 a0", "Unknown operator 0xB7"),
        ("33 c1 c1 a0", "leaves 2 values"),
        ("32 a4 a0", "lacks operands"),
        ("34 c2 c1 a2 a0", "first operand other than 0"),
        ("34 32 c1 a0 a0", "holds another as an operand"),
        ("33 c1 a0 c1", "does not end where its size says"),
        ("82 c1 00", "Expected a statement"),
        ("66 86 0d 00 00 c1 00", "Expected an option"),
        ("75 01 00 51 61 00", "Expected a value"),
    ],
)
def test_malformed_bytecode_is_reported(data: str, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        decode_value(bytes.fromhex(data))


@pytest.mark.parametrize("data", [b"a\0b", b"a" * 255])
def test_strings_the_bytecode_cannot_hold_are_refused(data: bytes) -> None:
    with pytest.raises(ValueError, match="at most 254 bytes and no NUL"):
        String(data)


def test_integers_beyond_32_bits_are_refused() -> None:
    with pytest.raises(ValueError, match="does not fit in 32 bits"):
        encode_node(Int(1 << 31))
