"""The listing of a GCX script: its code as text to read, edit and compile back.

A listing names the variant of the file, its timestamp, its seed when plain and
its number of glyphs. It then holds the procs in the order the file stores them,
main, and the resources in order: strings in the markup of the PS2 encoding and
lists of values, each followed by a comment with the res: number code refers to
it by. Statements end with a semicolon; whitespace and // comments are free.
Names are printed as such when known, built in or from a dictionary, else as
their strcode: #0C4FAF.
"""

import re
from collections.abc import Mapping

from mgtools.mc.gcx.legacy import decode_legacy
from mgtools.mc.gcx.nodes import (
    Argument,
    Binary,
    Block,
    Call,
    Command,
    Element,
    Expression,
    Int,
    Operand,
    Operator,
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
from mgtools.mc.gcx.script import GLYPH_BYTES, DataResource, Script, StringResource
from mgtools.mc.gcx.strcode import strcode

# The commands, names whose use shows their meaning, and the MGS3 stages that key
# the table of location names.
_KNOWN_NAMES = """
    chara command if load print return switch ending init scenerio varsave
    v001a v002a v003a v004a v005a v006a v006b v007a s001a s002a s003a s004a s005a
    s006a s006b s012a s021a s022a s023a s031a s032a s032b s033a s041a s042a s043a
    s044a s045a s051a s051b s052a s052b s053a s055a s056a s061a s062a s063a s063b
    s064a s064b s065a s065b s066a s071a s072a s072b s073a s073b s074a s075a s081a
    s081b s091a s091b s091c s092a s092b s092c s093a s093b s093c s094a s094b s094c
    s101a s101b s111a s112a s113a s121a s122a s141a s151a s152a s161a s162a s163a
    s163b s171a s171b s181a s182a s183a s191a s191b s192a s201a s211a
"""
_NAMES = {strcode(name): name for name in _KNOWN_NAMES.split()}
# Binary operators with their precedence, as in C.
BINARY_OPERATORS = {
    Operator.ASSIGN: ("=", 0),
    Operator.LOGICAL_OR: ("||", 1),
    Operator.LOGICAL_AND: ("&&", 2),
    Operator.OR: ("|", 3),
    Operator.XOR: ("^", 4),
    Operator.AND: ("&", 5),
    Operator.EQUAL: ("==", 6),
    Operator.NOT_EQUAL: ("!=", 6),
    Operator.LESS: ("<", 7),
    Operator.LESS_EQUAL: ("<=", 7),
    Operator.GREATER: (">", 7),
    Operator.GREATER_EQUAL: (">=", 7),
    Operator.SHIFT_LEFT: ("<<", 8),
    Operator.SHIFT_RIGHT: (">>", 8),
    Operator.ADD: ("+", 9),
    Operator.SUBTRACT: ("-", 9),
    Operator.MULTIPLY: ("*", 10),
    Operator.DIVIDE: ("/", 10),
    Operator.MODULO: ("%", 10),
}
UNARY_OPERATORS = {Operator.NEGATE: "-", Operator.NOT: "!", Operator.INVERT: "~"}
REGION_LETTERS = {Region.GLOBAL: "g", Region.LOCAL: "l", Region.SYSTEM: "s", Region.LINK: "k"}
# Short, byte, char, flag, strcode and int.
TYPE_LETTERS = dict(zip(VariableType, "wbcfsi", strict=True))

_LANGUAGE_CALL = 0x8000
_INDENT = "    "
_COMMAND_START = re.compile(r"[A-Za-z_#]")
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n"}


def format_listing(script: Script, names: Mapping[int, str] | None = None) -> str:
    """Return the listing of a script, without its UTF-8 texts and glyph pixels.

    Args:
        script: The script to list.
        names: Names to write for strcodes, taking precedence over the built-in ones; each
            must hash to its strcode, as read_dictionary ensures, for the listing to compile back.
    """
    lister = _Lister({**_NAMES, **(names or {})})
    lines = [
        f"gcx {'bluepoint' if script.bluepoint else 'plain'}",
        f"timestamp 0x{script.timestamp:08X}",
    ]
    if not script.bluepoint:
        lines.append(f"seed 0x{script.seed:08X}")
    lines.append(f"glyphs {len(script.glyphs) // GLYPH_BYTES}")
    for proc in script.procs:
        language = f" lang 0x{proc.language:02X}" if proc.language else ""
        lines += ["", f"proc {proc.id}{language} {lister.block(proc.body, 0)}"]
    lines += ["", f"main {lister.block(script.main, 0)}", ""]
    for index, resource in enumerate(script.resources):
        match resource:
            case StringResource(legacy):
                text = f"string {_quote(decode_legacy(legacy))}"
            case DataResource(values):
                text = f"data {{{lister.values(values, 0)}}}"
        lines.append(f"{text}  // res:{index}")
    return "\n".join(lines) + "\n"


class _Lister:
    """Writes code, naming the strcodes it has names for."""

    def __init__(self, names: Mapping[int, str]) -> None:
        self._names = names

    def block(self, block: Block, depth: int) -> str:
        """Return a block in braces, its statements one level deeper than depth."""
        if not block.statements:
            return "{}"
        inner = _INDENT * (depth + 1)
        lines = "".join(f"{inner}{self.statement(s, depth + 1)};\n" for s in block.statements)
        return f"{{\n{lines}{_INDENT * depth}}}"

    def statement(self, statement: Statement, depth: int) -> str:
        """Return a statement without its semicolon, its blocks indented from depth."""
        match statement:
            case Call(proc, args):
                target = f"@0x{proc:04X}" if proc & _LANGUAGE_CALL else f"@{proc}"
                words = [target, self.values(args, depth)]
            case Command(code, args, options):
                words = [self.name(code), self.values(args, depth)]
                for option in options:
                    words += [f"-{option.letter}", self.values(option.values, depth)]
            case Expression(root):
                text = self.operand(root, depth)
                # Else the statement would read as a command.
                return f"({text})" if _COMMAND_START.match(text) else text
        return " ".join(word for word in words if word)

    def values(self, values: tuple[Value, ...], depth: int) -> str:
        """Return values separated by spaces, their blocks indented from depth."""
        return " ".join(self.value(value, depth) for value in values)

    def value(self, value: Value, depth: int) -> str:
        """Return a value as the listing writes it, its blocks indented from depth."""
        match value:
            case Int(number):
                return str(number)
            case Symbol(number):
                return f"t:0x{number:08X}"
            case StrCode(code):
                return self.name(code)
            case String(data):
                return _quote(_inline_text(data))
            case ProcRef(proc):
                return f"&{proc}"
            case ResourceRef(index):
                return f"res:{index}"
            case Argument(index):
                return f"$arg{index}"
            case Variable():
                return _variable(value, "")
            case Element(variable, size, index):
                sized = _variable(variable, f":{self.value(size, depth)}")
                return f"{sized}[{self.value(index, depth)}]"
            case Expression(root):
                return f"({self.operand(root, depth)})"
            case Block():
                return self.block(value, depth)

    def operand(self, operand: Operand, depth: int, outer: int = -1, on_right: bool = False) -> str:
        """Return an operand, in parentheses where the operator around it needs them."""
        match operand:
            case Unary(operator, inner):
                return f"{UNARY_OPERATORS[operator]}({self.operand(inner, depth)})"
            case Binary(operator, left, right):
                symbol, rank = BINARY_OPERATORS[operator]
                text = (
                    f"{self.operand(left, depth, rank)} {symbol} "
                    f"{self.operand(right, depth, rank, on_right=True)}"
                )
                # Assignments group from the right, the other operators from the left.
                grouped_right = operator is Operator.ASSIGN
                if rank < outer or (rank == outer and on_right != grouped_right):
                    return f"({text})"
                return text
        return self.value(operand, depth)

    def name(self, code: int) -> str:
        """Return the name of a strcode, or the strcode itself after # when it has none."""
        return self._names.get(code, f"#{code:06X}")


def _variable(variable: Variable, size: str) -> str:
    """Return a variable as $, its region and type letters, and its place in brackets."""
    bit = f".{variable.bit}" if variable.type is VariableType.FLAG else ""
    letters = REGION_LETTERS[variable.region] + TYPE_LETTERS[variable.type]
    return f"${letters}[0x{variable.offset:04X}{bit}{size}]"


def _inline_text(data: bytes) -> str:
    """Return a string in code as EUC-JP text, or as ASCII if that would not round-trip."""
    text = data.decode("euc_jp", "surrogateescape")
    # A few sequences decode to a character that encodes differently.
    if text.encode("euc_jp", "surrogateescape") != data:
        return data.decode("ascii", "surrogateescape")
    return text


def _quote(text: str) -> str:
    """Return text in double quotes, escaping what would end it or not show."""
    return '"' + "".join(_escaped(character) for character in text) + '"'


def _escaped(character: str) -> str:
    """Return a character as it stands between quotes, escaped where needed."""
    code = ord(character)
    if character in _ESCAPES:
        return _ESCAPES[character]
    if 0xDC80 <= code <= 0xDCFF:
        return f"\\x{code - 0xDC00:02X}"
    # Control and private use characters would be invisible.
    if code < 0x20 or 0x7F <= code < 0xA0 or 0xE000 <= code <= 0xF8FF:
        return f"\\u{code:04X}"
    return character
