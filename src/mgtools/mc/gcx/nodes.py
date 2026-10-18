"""The values and statements of GCL bytecode, as reading compiled scripts gives them."""

from dataclasses import dataclass
from enum import IntEnum


class Operator(IntEnum):
    """An operator of expressions, which takes two operands from the stack."""

    NEGATE = 1
    NOT = 2
    INVERT = 3
    ADD = 4
    SUBTRACT = 5
    MULTIPLY = 6
    DIVIDE = 7
    MODULO = 8
    SHIFT_LEFT = 9
    SHIFT_RIGHT = 10
    EQUAL = 11
    NOT_EQUAL = 12
    LESS = 13
    LESS_EQUAL = 14
    GREATER = 15
    GREATER_EQUAL = 16
    OR = 17
    AND = 18
    XOR = 19
    LOGICAL_OR = 20
    LOGICAL_AND = 21
    ASSIGN = 22


class Region(IntEnum):
    """The memory a variable lives in."""

    GLOBAL = 0
    LOCAL = 1
    SYSTEM = 4
    LINK = 8


class VariableType(IntEnum):
    """The type of a variable, the low nibble of its lead byte."""

    SHORT = 1
    BYTE = 2
    CHAR = 3
    FLAG = 4
    STRCODE = 6
    INT = 9


@dataclass(frozen=True, slots=True)
class Int:
    """A signed 32-bit integer."""

    value: int


@dataclass(frozen=True, slots=True)
class Symbol:
    """A 32-bit value of unknown meaning, such as the id of a piece of music."""

    value: int


@dataclass(frozen=True, slots=True)
class StrCode:
    """A name, as its strcode."""

    code: int


@dataclass(frozen=True, slots=True)
class String:
    """A string in code, without its terminating NUL."""

    data: bytes

    def __post_init__(self) -> None:
        """Refuse data that a string in code cannot hold."""
        if len(self.data) > 254 or b"\0" in self.data:
            msg = f"A string in code holds at most 254 bytes and no NUL: {self.data!r}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ProcRef:
    """A proc passed as a value, by its number."""

    proc: int


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """A resource of the script passed as a value, by its index."""

    index: int


@dataclass(frozen=True, slots=True)
class Argument:
    """An argument of the proc being run."""

    index: int


@dataclass(frozen=True, slots=True)
class Variable:
    """A variable: its type, where it lives, and for a flag the bit it is."""

    type: VariableType
    region: Region
    offset: int
    bit: int = 0


@dataclass(frozen=True, slots=True)
class Element:
    """An element of the array of a size that starts at a variable."""

    variable: Variable
    size: Value
    index: Value


@dataclass(frozen=True, slots=True)
class Unary:
    """A unary operator and its operand, within an expression."""

    operator: Operator
    operand: Operand


@dataclass(frozen=True, slots=True)
class Binary:
    """A binary operator and its operands, within an expression."""

    operator: Operator
    left: Operand
    right: Operand


@dataclass(frozen=True, slots=True)
class Expression:
    """An expression, as the tree its reverse Polish notation builds."""

    root: Operand


@dataclass(frozen=True, slots=True)
class Block:
    """A list of statements, such as the body of a proc or a value passed to if."""

    statements: tuple[Statement, ...]


@dataclass(frozen=True, slots=True)
class Option:
    """An option of a command: a letter and its values."""

    letter: str
    values: tuple[Value, ...]


@dataclass(frozen=True, slots=True)
class Command:
    """A command, named by its strcode; if and switch are commands too."""

    code: int
    args: tuple[Value, ...]
    options: tuple[Option, ...] = ()


@dataclass(frozen=True, slots=True)
class Call:
    """A call of a proc by its number; bit 15 picks the proc of the language."""

    proc: int
    args: tuple[Value, ...] = ()


type Value = (
    Int
    | Symbol
    | StrCode
    | String
    | ProcRef
    | ResourceRef
    | Argument
    | Variable
    | Element
    | Expression
    | Block
)
type Operand = Value | Unary | Binary
type Statement = Command | Call | Expression
type Node = Value | Statement | Option
