from dataclasses import replace

import pytest

from mgtools.mc.gcx.listing import format_listing
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
    Region,
    ResourceRef,
    Statement,
    StrCode,
    String,
    Symbol,
    Unary,
    Variable,
    VariableType,
)
from mgtools.mc.gcx.parser import parse_listing
from mgtools.mc.gcx.script import (
    GLYPH_BYTES,
    DataResource,
    Proc,
    Script,
    StringResource,
)
from mgtools.mc.gcx.strcode import strcode

HEADER = "gcx plain timestamp 0 seed 0 glyphs 0\n"
FIRST = Variable(VariableType.INT, Region.GLOBAL, 0x0001)
SECOND = Variable(VariableType.INT, Region.GLOBAL, 0x0002)
FLAG = Variable(VariableType.FLAG, Region.LOCAL, 0x0DD2, 7)
TABLE = Variable(VariableType.SHORT, Region.LINK, 0x0156)


def with_main(*statements: Statement) -> Script:
    return Script(False, 1, 2, (), Block(statements), (), b"")


SCRIPT = Script(
    bluepoint=False,
    timestamp=0x43E6D30F,
    seed=0x4369EA9C,
    procs=(
        Proc(2, Block(())),
        Proc(
            1,
            Block(
                (
                    Command(
                        strcode("if"),
                        (
                            Expression(Binary(Operator.NOT_EQUAL, FLAG, Int(0))),
                            Block(()),
                        ),
                        (Option("e", (Block((Call(0x8014),)),)),),
                    ),
                    Command(
                        strcode("print"),
                        (
                            String("音楽再生".encode("euc_jp")),
                            String(b'say "hi"\\\n\t'),
                            String(b"\x8f\xa2\xb7\xff"),
                        ),
                    ),
                    Command(
                        0x99F754,
                        (Int(-32768), Int(-1), Int(1 << 20), StrCode(0x48C688)),
                        (Option("c", (Symbol(0x0D30D133), ProcRef(7), ResourceRef(44))),),
                    ),
                    Call(
                        2,
                        (
                            Argument(1),
                            Element(TABLE, Int(131), Expression(Argument(2))),
                        ),
                    ),
                    Expression(
                        Binary(
                            Operator.ASSIGN,
                            FIRST,
                            Block((Command(0xD8361E, ()), Call(2, (Int(70000),)))),
                        )
                    ),
                )
            ),
            language=0x10,
        ),
    ),
    main=Block((Call(1), Command(strcode("load"), (String(b"title"),)))),
    resources=(
        StringResource(b'Say "hi" {now}\\ \x8c\x01\x1f\x0f\n'),
        DataResource((Int(0), String(b"NONE"), Symbol(0x06C0B43F), Block(()))),
        DataResource(()),
    ),
    glyphs=bytes(2 * GLYPH_BYTES),
)


def test_a_listing_reads_back_as_the_script_it_shows() -> None:
    assert parse_listing(format_listing(SCRIPT)) == SCRIPT


def test_a_bluepoint_listing_leaves_out_the_texts_and_the_seed() -> None:
    bluepoint = replace(SCRIPT, bluepoint=True, seed=0, resources=(StringResource(b"Yes", "Sure"),))

    listing = format_listing(bluepoint)

    assert listing.startswith("gcx bluepoint\ntimestamp 0x43E6D30F\nglyphs 2\n")
    assert "Sure" not in listing
    assert parse_listing(listing) == replace(bluepoint, resources=(StringResource(b"Yes"),))
    with pytest.raises(ValueError, match="expected 'glyphs', found 'seed'"):
        parse_listing(listing.replace("glyphs", "seed 0 glyphs", 1))


def test_listings_show_names_variables_and_markup_readably() -> None:
    listing = format_listing(SCRIPT)

    assert "proc 2 {}\n\nproc 1 lang 0x10 {\n    if ($lf[0x0DD2.7] != 0) {} -e {" in listing
    assert 'print "音楽再生" "say \\"hi\\"\\\\\\n\\u0009" "\\x8F\\xA2\\xB7\\xFF";' in listing
    assert "#99F754 -32768 -1 1048576 s001a -c t:0x0D30D133 &7 res:44;" in listing
    assert "@2 $arg1 $kw[0x0156:131][($arg2)];" in listing
    assert '\nstring "Say \\"hi\\" {7B}now{7D}\\\\ {8C01}é\\n"  // res:0\n' in listing
    assert '\ndata {0 "NONE" t:0x06C0B43F {}}  // res:1\ndata {}  // res:2\n' in listing


@pytest.mark.parametrize(
    ("operand", "text"),
    [
        (
            Binary(Operator.SUBTRACT, FIRST, Binary(Operator.SUBTRACT, SECOND, Int(3))),
            "$gi[0x0001] - ($gi[0x0002] - 3)",
        ),
        (
            Binary(Operator.SUBTRACT, Binary(Operator.SUBTRACT, FIRST, SECOND), Int(3)),
            "$gi[0x0001] - $gi[0x0002] - 3",
        ),
        (
            Binary(Operator.ASSIGN, FIRST, Binary(Operator.ASSIGN, SECOND, Int(1))),
            "$gi[0x0001] = $gi[0x0002] = 1",
        ),
        (
            Binary(Operator.ASSIGN, Binary(Operator.ASSIGN, FIRST, SECOND), Int(1)),
            "($gi[0x0001] = $gi[0x0002]) = 1",
        ),
        (
            Binary(Operator.MULTIPLY, Binary(Operator.ADD, FIRST, SECOND), Int(2)),
            "($gi[0x0001] + $gi[0x0002]) * 2",
        ),
        (
            Binary(Operator.ADD, FIRST, Binary(Operator.MULTIPLY, SECOND, Int(2))),
            "$gi[0x0001] + $gi[0x0002] * 2",
        ),
        (
            Binary(Operator.AND, Binary(Operator.SHIFT_RIGHT, FIRST, Int(16)), Int(15)),
            "$gi[0x0001] >> 16 & 15",
        ),
        (
            Binary(
                Operator.LOGICAL_AND,
                Unary(Operator.NOT, FIRST),
                Unary(Operator.NEGATE, Int(5)),
            ),
            "!($gi[0x0001]) && -(5)",
        ),
        (Int(-5), "-5"),
        (Binary(Operator.EQUAL, StrCode(0xABCDEF), Int(1)), "(#ABCDEF == 1)"),
        (
            Binary(Operator.EQUAL, StrCode(strcode("init")), FIRST),
            "(init == $gi[0x0001])",
        ),
    ],
)
def test_expressions_take_parentheses_only_where_needed(operand: Operand, text: str) -> None:
    script = with_main(Expression(operand))

    listing = format_listing(script)

    assert f"main {{\n    {text};\n}}" in listing
    assert parse_listing(listing) == script


def test_whitespace_and_comments_are_free() -> None:
    compact = (
        "gcx plain timestamp 0x1 seed 0x2 glyphs 0 proc 1{if($gi[0x0010]>=-2)"
        '{@0x8014;}-e{print "a  b";};}main{@1 $arg1;}'
        'string "x // y"data{-1 t:0x5 res:0}'
    )
    spaced = """
        // Comments run to the end of the line.
        gcx   plain
        timestamp 1 seed 2 glyphs 0  // numbers may be decimal or hex
        proc 1 {
            if ( $gi[ 0x10 ] >= - 2 ) { @ 0x8014 ; } - e { print "a  b" ; } ;
        }
        main { @ 1 $arg1 ; }
        string "x // y"  // but // in a string is no comment
        data { - 1 t : 5 res : 0 }
    """

    assert parse_listing(compact) == parse_listing(spaced)


def test_names_hash_to_their_strcode() -> None:
    script = parse_listing(HEADER + "main { scenerio v001a #0C4FAF; }")

    stage = StrCode(strcode("v001a"))
    assert script.main == Block((Command(0x180720, (stage, StrCode(0x0C4FAF))),))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("main {\n    print 1\n}", "Line 4: expected ';', found '}'"),
        ("main { print ?; }", "Line 2: unexpected '\\?'"),
        ("main { $zz[0x1] = 1; }", "Line 2: unknown variable \\$zz"),
        ("main { $gi[0x1.2] = 1; }", "only flags take a bit"),
        ("main { $gi[0x10000] = 1; }", "a variable offset must be from 0 to 65535"),
        ("main { print 2147483648; }", "an integer must be from"),
        ("main { print $arg15; }", "arguments are numbered from 0 to 14"),
        ("main { print x:1; }", "unknown kind of value x:"),
        ('main { print "\\q"; }', "unknown escape \\\\q"),
        ('main { print "€"; }', "'€' has no code in EUC-JP"),
        ("main { print -ab; }", "expected an option letter, found 'ab'"),
        ('main {}\nstring "ą"', "Line 3: 'ą' .* has no code in the PS2 encoding"),
        (
            'main {}\nstring "{8C02}"',
            "Line 3: the string uses glyph 2, but the header has 0",
        ),
        (f'main {{ print "{"a" * 255}"; }}', "Line 2: .* at most 254 bytes"),
        ("main {}\nmain {}", "Line 3: the listing has a second main"),
        ("proc 1 {}", "the listing has no main"),
        ("main {} end", "expected proc, main, string or data, found 'end'"),
    ],
)
def test_mistakes_are_reported_with_their_line(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_listing(HEADER + text)
