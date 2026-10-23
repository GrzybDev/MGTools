"""Reading a listing back into the GCX script it describes."""

import re
from dataclasses import dataclass

from mgtools.mc.gcx.legacy import encode_legacy, glyphs_used
from mgtools.mc.gcx.listing import BINARY_OPERATORS, REGION_LETTERS, TYPE_LETTERS, UNARY_OPERATORS
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
    Option,
    ProcRef,
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
from mgtools.mc.gcx.script import (
    GLYPH_BYTES,
    DataResource,
    Proc,
    Resource,
    Script,
    StringResource,
)
from mgtools.mc.gcx.strcode import strcode

_BINARY_OF = {symbol: (operator, rank) for operator, (symbol, rank) in BINARY_OPERATORS.items()}
_UNARY_OF = {symbol: operator for operator, symbol in UNARY_OPERATORS.items()}
_REGION_OF = {letter: region for region, letter in REGION_LETTERS.items()}
_TYPE_OF = {letter: kind for kind, letter in TYPE_LETTERS.items()}

_U32 = 0xFFFF_FFFF
_U16 = 0xFFFF
# Codes 8C01 to 8CFF and 8D01 to 8DFF name the glyphs.
_MAX_GLYPHS = 510
_UNESCAPES = {"\\": "\\", '"': '"', "n": "\n"}
_ESCAPE = re.compile(r"\\(?:x([0-9A-Fa-f]{2})|u([0-9A-Fa-f]{4})|(.))", re.DOTALL)
_TOKEN = re.compile(
    r"""
      (?P<space>\s+|//[^\n]*)
    | (?P<string>"(?:[^"\\\n]|\\.)*")
    | (?P<number>0x[0-9A-Fa-f]+|[0-9]+)
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<hash>\#[0-9A-Fa-f]{6})
    | (?P<variable>\$[A-Za-z0-9]+)
    | (?P<symbol><<|>>|==|!=|<=|>=|\|\||&&|[-+*/%<>|&^=!~(){}\[\];:.@])
    """,
    re.VERBOSE,
)
_VALUE_KINDS = frozenset({"number", "string", "name", "hash", "variable"})


def parse_listing(text: str) -> Script:
    """Return the script of a listing, with blank glyphs and no UTF-8 texts.

    Args:
        text: The listing, as format_listing writes it.
    """
    return _Parser(text).script()


def is_name(text: str) -> bool:
    """Return whether a listing reads text as a name, which compiles to its strcode.

    Args:
        text: The text to check.
    """
    match = _TOKEN.fullmatch(text)
    return match is not None and match.lastgroup == "name"


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    line: int

    def error(self, message: str) -> ValueError:
        """Return an error with message at the token's line, for the caller to raise."""
        return ValueError(f"Line {self.line}: {message}")

    def unexpected(self, expected: str) -> ValueError:
        """Return an error saying the token stands where expected should."""
        found = repr(self.text) if self.kind != "end" else "the end"
        return self.error(f"expected {expected}, found {found}")


class _Parser:
    def __init__(self, text: str) -> None:
        self._tokens = _tokens(text)
        self._next = 0
        self._glyphs = 0

    def script(self) -> Script:
        """Parse the whole listing, its glyphs blank in the number its header gives."""
        self.expect("gcx")
        variant = self.take()
        if variant.text not in ("bluepoint", "plain"):
            raise variant.unexpected("bluepoint or plain")
        bluepoint = variant.text == "bluepoint"
        self.expect("timestamp")
        timestamp = self.integer(0, _U32, "the timestamp")
        seed = 0
        if not bluepoint:
            self.expect("seed")
            seed = self.integer(0, _U32, "the seed")
        self.expect("glyphs")
        self._glyphs = self.integer(0, _MAX_GLYPHS, "the number of glyphs")
        procs: list[Proc] = []
        resources: list[Resource] = []
        main = None
        while (token := self.take()).kind != "end":
            if token.text == "proc":
                number = self.integer(1, _U16, "a proc number")
                language = self.integer(0, 0xFF, "a language") if self.accept("lang") else 0
                procs.append(Proc(number, self.block(), language))
            elif token.text == "main":
                if main is not None:
                    raise token.error("the listing has a second main")
                main = self.block()
            elif token.text == "string":
                resources.append(self.string())
            elif token.text == "data":
                resources.append(self.data())
            else:
                raise token.unexpected("proc, main, string or data")
        if main is None:
            raise self.peek().error("the listing has no main")
        blank_glyphs = bytes(self._glyphs * GLYPH_BYTES)
        return Script(
            bluepoint,
            timestamp,
            seed,
            tuple(procs),
            main,
            tuple(resources),
            blank_glyphs,
        )

    def string(self) -> StringResource:
        """Parse the markup of a string resource, refusing glyphs the header lacks."""
        token = self.take()
        if token.kind != "string":
            raise token.unexpected("a string")
        try:
            legacy = encode_legacy(_unquote(token))
        except ValueError as error:
            raise token.error(str(error)) from error
        if (used := glyphs_used(legacy)) > self._glyphs:
            msg = f"the string uses glyph {used}, but the header has {self._glyphs}"
            raise token.error(msg)
        return StringResource(legacy)

    def data(self) -> DataResource:
        """Parse the values of a data resource, in braces."""
        self.expect("{")
        values = self.values()
        self.expect("}")
        return DataResource(values)

    def block(self) -> Block:
        self.expect("{")
        statements = []
        while not self.accept("}"):
            statements.append(self.statement())
            self.expect(";")
        return Block(tuple(statements))

    def statement(self) -> Statement:
        """Parse a call, a command with its options, or an expression."""
        token = self.peek()
        if self.accept("@"):
            return Call(self.integer(0, _U16, "a proc number"), self.values())
        if token.kind not in ("name", "hash"):
            return Expression(self.expression())
        self.take()
        code = _strcode(token)
        args = self.values()
        options = []
        while self.accept("-"):
            letter = self.take()
            if letter.kind != "name" or len(letter.text) != 1:
                raise letter.unexpected("an option letter")
            options.append(Option(letter.text, self.values()))
        return Command(code, args, tuple(options))

    def expression(self, lowest: int = 0) -> Operand:
        """Parse an expression whose binary operators rank lowest or higher."""
        left = self.operand()
        while (entry := _BINARY_OF.get(self.peek().text)) and entry[1] >= lowest:
            operator, rank = entry
            self.take()
            right = self.expression(rank if operator is Operator.ASSIGN else rank + 1)
            left = Binary(operator, left, right)
        return left

    def operand(self) -> Operand:
        """Parse a unary operation, an expression in parentheses or a value."""
        token = self.peek()
        if token.text in _UNARY_OF and self.peek(1).text == "(":
            self.take()
            return Unary(_UNARY_OF[token.text], self.parenthesized())
        if token.text == "(":
            return self.parenthesized()
        return self.value()

    def parenthesized(self) -> Operand:
        self.expect("(")
        operand = self.expression()
        self.expect(")")
        return operand

    def values(self) -> tuple[Value, ...]:
        """Parse values up to the first token that cannot start one."""
        values = []
        while self.at_value():
            values.append(self.value())
        return tuple(values)

    def at_value(self) -> bool:
        """Return whether the next token starts a value."""
        token = self.peek()
        if token.text == "-":
            return self.peek(1).kind == "number"
        return token.kind in _VALUE_KINDS or token.text in ("&", "(", "{")

    def value(self) -> Value:
        token = self.peek()
        if token.kind == "number" or token.text == "-":
            return Int(self.integer(-(1 << 31), (1 << 31) - 1, "an integer"))
        if token.text == "{":
            return self.block()
        if token.text == "(":
            return Expression(self.parenthesized())
        self.take()
        if token.kind == "name" and self.accept(":"):
            return self.typed(token)
        if token.kind in ("name", "hash"):
            return StrCode(_strcode(token))
        if token.kind == "string":
            text = _unquote(token)
            try:
                return String(text.encode("euc_jp", "surrogateescape"))
            except UnicodeEncodeError as error:
                character = text[error.start]
                raise token.error(f"{character!r} has no code in EUC-JP") from error
            except ValueError as error:
                raise token.error(str(error)) from error
        if token.kind == "variable":
            return self.variable(token)
        if token.text == "&":
            return ProcRef(self.integer(0, _U16, "a proc number"))
        raise token.unexpected("a value")

    def typed(self, token: _Token) -> Value:
        """Parse a symbol or a resource reference, after token naming its kind and a colon."""
        if token.text == "t":
            return Symbol(self.integer(0, _U32, "a symbol"))
        if token.text == "res":
            return ResourceRef(self.integer(0, _U16, "a resource number"))
        raise token.error(f"unknown kind of value {token.text}:")

    def variable(self, token: _Token) -> Value:
        """Parse an argument, a variable or an array element named by a $ token."""
        name = token.text[1:]
        if name.startswith("arg") and name[3:].isdigit():
            if (number := int(name[3:])) > 14:
                raise token.error("arguments are numbered from 0 to 14")
            return Argument(number)
        region, kind = _REGION_OF.get(name[:1]), _TYPE_OF.get(name[1:])
        if region is None or kind is None:
            raise token.error(f"unknown variable {token.text}")
        self.expect("[")
        offset = self.integer(0, _U16, "a variable offset")
        bit = self.integer(0, 15, "a bit") if self.accept(".") else 0
        if bit and kind is not VariableType.FLAG:
            raise token.error("only flags take a bit")
        variable = Variable(kind, region, offset, bit)
        if not self.accept(":"):
            self.expect("]")
            return variable
        size = self.value()
        self.expect("]")
        self.expect("[")
        index = self.value()
        self.expect("]")
        return Element(variable, size, index)

    def integer(self, low: int, high: int, what: str) -> int:
        """Parse an integer from low to high; what names it in errors."""
        negative = self.accept("-")
        token = self.take()
        if token.kind != "number":
            raise token.unexpected(what)
        value = int(token.text, 16 if token.text.startswith("0x") else 10)
        value = -value if negative else value
        if not low <= value <= high:
            raise token.error(f"{what} must be from {low} to {high}, not {value}")
        return value

    def peek(self, ahead: int = 0) -> _Token:
        """Return the token ahead places after the next, or the end token past the end."""
        return self._tokens[min(self._next + ahead, len(self._tokens) - 1)]

    def take(self) -> _Token:
        token = self.peek()
        self._next += 1
        return token

    def accept(self, text: str) -> bool:
        """Take the next token if it reads text, returning whether it did."""
        if self.peek().text == text:
            self._next += 1
            return True
        return False

    def expect(self, text: str) -> None:
        """Take the next token, refusing one that does not read text."""
        if not self.accept(text):
            raise self.peek().unexpected(repr(text))


def _strcode(token: _Token) -> int:
    """Return the strcode of a name, or the one a # token writes in hex."""
    return int(token.text[1:], 16) if token.kind == "hash" else strcode(token.text)


def _unquote(token: _Token) -> str:
    """Return the text of a string token without its quotes and escapes."""

    def unescape(match: re.Match[str]) -> str:
        if match[1]:
            # Bytes from 0x80 stand for themselves, as surrogateescape keeps them.
            byte = int(match[1], 16)
            return chr(byte if byte < 0x80 else 0xDC00 + byte)
        if match[2]:
            return chr(int(match[2], 16))
        if match[3] in _UNESCAPES:
            return _UNESCAPES[match[3]]
        raise token.error(f"unknown escape \\{match[3]}")

    return _ESCAPE.sub(unescape, token.text[1:-1])


def _tokens(text: str) -> list[_Token]:
    """Split a listing into tokens, without whitespace and comments, ending with an end token."""
    tokens = []
    line = 1
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:
            raise ValueError(f"Line {line}: unexpected {text[position]!r}")
        if match.lastgroup != "space":
            tokens.append(_Token(match.lastgroup or "", match[0], line))
        line += match[0].count("\n")
        position = match.end()
    tokens.append(_Token("end", "", line))
    return tokens
