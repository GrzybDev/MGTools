# GCX scripts

A GCX file is a compiled GCL script of a stage of the Master Collection. It holds the code of the stage (procedures and
a main block), the resources the code refers to (strings and lists of values) and the glyphs its strings use beyond the
PS2 character set. `mgtools gcx export` turns a GCX file into a folder with a listing, a translation document and a PNG
image, and `mgtools gcx import` compiles that folder back to the same bytes (see [Usage](../README.md#gcx-scripts)).

The engine reads a script from the `_bp` folder beside the path its file list names when a copy is there, such as
`fr/stage/{mg1,mg2}/cache/_bp/00180720.gcx` and `assets/gcx/fr/_bp/*.gcx`; these are Bluepoint files. The plain copies
beside the `_bp` folders, such as `cache/00180720.gcx`, are then not read. [File lists](manifest.md) explains how
the engine picks the file.

Every number is little-endian unless a table says otherwise.

Variants
--------

A GCX file is either plain or Bluepoint. Bluepoint files start with `LCGB` and carry the UTF-8 text of each string next
to its PS2 encoding.

| Property               | Plain                            | Bluepoint                                             |
|------------------------|----------------------------------|-------------------------------------------------------|
| Magic                  | none                             | `LCGB` (4C 43 47 42)                                  |
| Header after the procs | 0x14 bytes                       | 0x18 bytes                                            |
| UTF-8 texts            | none                             | one per string resource, before the resource table    |
| Resource area          | encrypted when the seed is not 0 | never encrypted, the seed is 0                        |
| Glyph section          | size, glyphs                     | section size, size, glyphs without their last 4 bytes |
| File padding (zeros)   | to a multiple of 16 bytes        | to a multiple of 4 bytes                              |

Overall layout
--------------

| Part            | Position                  | Description                                         |
|-----------------|---------------------------|-----------------------------------------------------|
| Magic           | 0 (Bluepoint only)        | `LCGB`                                              |
| Timestamp       | 0 or 4                    | u32, kept as it is                                  |
| Procedure table | after the timestamp       | a u32 per procedure, then FFFFFFFF                  |
| Header          | B, right after FFFFFFFF   | the offsets of the sections and the seed            |
| UTF-8 texts     | B + 0x18 (Bluepoint only) | the text section                                    |
| Resource table  | B + resource table offset | a u32 per resource                                  |
| Resource area   | B + resource area offset  | the resources, encrypted in plain files with a seed |
| Glyphs          | B + glyph offset          | the glyph section                                   |
| Code            | B + code offset           | the procedure bodies, then main                     |
| Padding         | to the end                | zero bytes                                          |

Every offset of the header counts from B, the position right after the FFFFFFFF that ends the procedure table. The
sections follow each other in this order with no gaps: MGTools refuses a file whose offsets are out of order, and a
plain file whose resource table does not start right after its 0x14-byte header.

### Procedure table

| Size | Type | Description                                                                     |
|------|------|---------------------------------------------------------------------------------|
| 4    | u32  | Entry of procedure 1: bits 24-31 the language, bits 0-23 the offset of its body |
| ...  | u32  | One entry per procedure, procedure n at index n - 1                             |
| 4    | u32  | FFFFFFFF, the end of the table                                                  |

The offset of a body counts from the start of the procedure bodies in the code section. The language is 0 for a
procedure every language runs, or a language id times 16 (0x10, 0x20 and so on) for a procedure of one language. The
bodies are stored back to back, but not necessarily in the order of their numbers; MGTools keeps their stored order.

### Header

| Offset | Size | Type | Description                                   |
|--------|------|------|-----------------------------------------------|
| B+0x00 | 4    | u32  | Offset of the code                            |
| B+0x04 | 4    | u32  | Offset of the resource table                  |
| B+0x08 | 4    | u32  | Offset of the resource area                   |
| B+0x0C | 4    | u32  | Offset of the glyph section                   |
| B+0x10 | 4    | u32  | Seed of the resource cipher, 0 for none       |
| B+0x14 | 4    | u32  | Bluepoint only: 0x18, the size of this header |

MGTools refuses a Bluepoint file whose word at B+0x14 is not 0x18 or whose seed is not 0.

### UTF-8 texts (Bluepoint)

The text section starts at B+0x18 and ends at the resource table.

| Offset | Size      | Type  | Description                                                                                          |
|--------|-----------|-------|------------------------------------------------------------------------------------------------------|
| 0x00   | 4         | u32   | Number of resources, the same as in the resource table                                               |
| 0x04   | 4 × count | u32   | Per resource, the offset of its text from the start of this section, or FFFFFFFF for a data resource |
| ...    | ...       | UTF-8 | The texts, each ending with a NUL byte, back to back in resource order                               |

Every string resource has a text and no data resource has one. The first text starts at 4 + 4 × count.

### Resource table

`count = (resource area offset - resource table offset) / 4` entries, one u32 per resource:

| Bits  | Description                                 |
|-------|---------------------------------------------|
| 24-31 | Kind: 0x80 a string, 0x00 a list of values  |
| 0-23  | Offset of the resource in the resource area |

Resources are numbered from 0 in table order; code refers to them by that number. Each resource starts where the one
before it ends.

### Resource area

| Resource              | Bytes                                                                      |
|-----------------------|----------------------------------------------------------------------------|
| String (0x80)         | The string in the [PS2 text encoding](#ps2-text-encoding), then a NUL byte |
| List of values (0x00) | [GCL values](#gcl-bytecode), then a 00 byte                                |

After the last resource, the area is padded to a multiple of 4 bytes with the letters of `FONT`: `F`, `FO` or `FON`.

In plain files with a seed other than 0, the whole area, padding included, is encrypted. Each byte is XORed with a byte
of a linear congruential generator whose state starts at the seed and advances before every byte:

```text
state = (state × 0x7D2B89DD + 0xCF9) mod 2^32
byte ^= (state >> 15) & 0xFF
```

The same operation decrypts. A seed of 0 leaves the area as it is.

### Glyphs

Glyphs are 24 × 24 pixels of 2 bits, 144 bytes each: four pixels per byte, the first in the two highest bits, rows of
6 bytes with no padding. Code 8C 01 of the PS2 encoding draws the first glyph.

| Variant   | Bytes                                                                                |
|-----------|--------------------------------------------------------------------------------------|
| Plain     | u32 N, the size of the glyphs (a multiple of 144), then the N bytes of the glyphs    |
| Bluepoint | u32 N + 4, the size of this section; then the plain section without its last 4 bytes |

The converter that made the Bluepoint files put the section size before the glyphs without making room for it, so a
Bluepoint file stores neither the last 4 bytes of the glyphs nor, with no glyphs, the u32 N: the section of a file
without glyphs is the single u32 4. MGTools reads the missing bytes as zeros and refuses to write a Bluepoint file
whose last glyph has pixels other than 0 in its last 16 pixels, the right two thirds of its bottom row.

### Code

| Size | Type | Description                         |
|------|------|-------------------------------------|
| 4    | u32  | Size of the procedure bodies        |
| ...  | GCL  | The bodies, each a [block](#blocks) |
| 4    | u32  | Size of main                        |
| ...  | GCL  | Main, a block                       |

Zero bytes then pad the file to a multiple of 16 bytes (plain) or 4 bytes (Bluepoint), counted from the start of the
file.

GCL bytecode
------------

The code is a tree of nodes. Each node starts with a lead byte that gives its kind:

| Lead byte  | Node                                                      | Listing                |
|------------|-----------------------------------------------------------|------------------------|
| C0-FF      | Small integer, (lead & 0x3F) - 1, from -1 to 62           | `-1` to `62`           |
| 01, 02, 09 | Integer with 2, 1 or 4 bytes after it                     | `300`                  |
| 06         | Name, as its [strcode](#name-hash-strcode)                | `print`, `#33CA52`     |
| 07         | String                                                    | `"Hello"`              |
| 08         | Procedure reference                                       | `&1`                   |
| 0A         | Symbol, a 32-bit value such as the id of a piece of music | `t:0x0000002A`         |
| 0E         | Resource reference                                        | `res:0`                |
| 1t         | Variable of type t                                        | `$gw[0x0010]`          |
| 2t         | Array element of type t                                   | `$li[0x0100:4][$arg1]` |
| 3s         | Expression (sized)                                        | `($gb[0x0002] + 1)`    |
| 40-4E      | Argument of the running procedure, 0 to 14                | `$arg0`                |
| 5s         | Option of a command (sized)                               | `-x 1`                 |
| 6s         | Command (sized)                                           | `print res:0`          |
| 7s         | Call of a procedure (sized)                               | `@1`, `@0x8001`        |
| 8s         | Block (sized)                                             | `{ ... }`              |

Values are integers, names, strings, procedure and resource references, symbols, arguments, variables, elements,
expressions and blocks. Statements, the contents of a block, are commands, calls and expressions. MGTools refuses any
other lead byte (such as 0x4F or 0x90), a statement where a value belongs and a value where a statement belongs.

### Sized nodes

Expressions, options, commands, calls and blocks give the size of the rest of the node in the low nibble s of their
lead byte:

| s    | Size of the rest of the node                |
|------|---------------------------------------------|
| 0-12 | s bytes                                     |
| 13   | the next byte, u8 (13 to 255)               |
| 14   | the next 2 bytes, u16 (256 to 65535)        |
| 15   | the next 3 bytes, u24 (65536 to 16 MiB - 1) |

The size counts the bytes after the size field to the end of the node. The compiler always chose the shortest form,
and MGTools reads and writes only that form: it refuses a size or an integer written longer than needed.

### Integers

| Range                               | Encoding               |
|-------------------------------------|------------------------|
| -1 to 62                            | one byte, 0xC1 + value |
| 63 to 255                           | 02, then u8            |
| other values from -32768 to 32767   | 01, then s16           |
| other values from -2^31 to 2^31 - 1 | 09, then s32           |

For example, 3 is C4, 255 is 02 FF, 256 is 01 00 01 and 70000 is 09 70 11 01 00.

### Other constants

| Lead | Bytes after it   | Meaning                                                          |
|------|------------------|------------------------------------------------------------------|
| 06   | u24              | A name, as its strcode                                           |
| 07   | u8 length, bytes | A string: the length counts the bytes and their NUL, at most 255 |
| 08   | u16              | A reference to a procedure, by number                            |
| 0A   | u32              | A symbol, such as the id of a piece of music                     |
| 0E   | u16              | A reference to a resource, by number                             |

A string in code holds at most 254 bytes and no NUL. The listing shows it as EUC-JP text, and bytes that form no EUC-JP
character as `\xHH`.

### Variables

| Offset | Size | Type   | Description                                                |
|--------|------|--------|------------------------------------------------------------|
| 0      | 1    | u8     | Lead byte: 0x10 + type (variable) or 0x20 + type (element) |
| 1      | 1    | u8     | Bits 4-7 the region, bits 0-3 the bit of a flag            |
| 2      | 2    | u16 BE | Offset of the variable in its region                       |

An element is followed by two values: the size of the array, then the index.

| Type | Name    | Listing letter |  | Region | Name   | Listing letter |
|------|---------|----------------|--|--------|--------|----------------|
| 1    | short   | `w`            |  | 0      | global | `g`            |
| 2    | byte    | `b`            |  | 1      | local  | `l`            |
| 3    | char    | `c`            |  | 4      | system | `s`            |
| 4    | flag    | `f`            |  | 8      | link   | `k`            |
| 6    | strcode | `s`            |  |        |        |                |
| 9    | int     | `i`            |  |        |        |                |

Only flags use the bit. MGTools refuses other types and regions, and a bit on a variable that is not a flag.

### Expressions

An expression holds its operands and operators in reverse Polish notation and ends with the byte A0. An operand is any
value but another expression. Bytes A1 to BF are operators, A0 + operator number:

| Number | Operator         | Listing | Precedence |
|--------|------------------|---------|------------|
| 1      | negate           | `-( )`  | unary      |
| 2      | logical not      | `!( )`  | unary      |
| 3      | bitwise not      | `~( )`  | unary      |
| 4      | add              | `+`     | 9          |
| 5      | subtract         | `-`     | 9          |
| 6      | multiply         | `*`     | 10         |
| 7      | divide           | `/`     | 10         |
| 8      | modulo           | `%`     | 10         |
| 9      | shift left       | `<<`    | 8          |
| 10     | shift right      | `>>`    | 8          |
| 11     | equal            | `==`    | 6          |
| 12     | not equal        | `!=`    | 6          |
| 13     | less             | `<`     | 7          |
| 14     | less or equal    | `<=`    | 7          |
| 15     | greater          | `>`     | 7          |
| 16     | greater or equal | `>=`    | 7          |
| 17     | bitwise or       | `\|`    | 3          |
| 18     | bitwise and      | `&`     | 5          |
| 19     | bitwise xor      | `^`     | 4          |
| 20     | logical or       | `\|\|`  | 1          |
| 21     | logical and      | `&&`    | 2          |
| 22     | assign           | `=`     | 0          |

Every operator takes two operands from the stack. The compiler gave the unary operators a first operand of 0 (byte
C1); MGTools refuses a unary operator with another first operand, and an expression that does not leave exactly one
value. The listing writes expressions in infix form with the precedence of C, higher binding tighter; assignments group
from the right, the other operators from the left.

### Commands and options

| Size   | Type         | Description                                                                                          |
|--------|--------------|------------------------------------------------------------------------------------------------------|
| 3      | u24          | The command's name, as its strcode                                                                   |
| 1 or 2 | u8 or u16 BE | Size of the arguments: one byte below 0x80; else two bytes whose first has bit 7 set, giving 15 bits |
| ...    | values       | The arguments                                                                                        |
| ...    | options      | Options, each a sized node with lead byte 0x5s                                                       |
| 1      | u8           | 00, the end of the command                                                                           |

An option holds an ASCII letter, then its values up to the end of its size. `if` and `switch` are commands too. The
arguments take at most 32767 bytes.

### Calls

| Size | Type   | Description                                                                                         |
|------|--------|-----------------------------------------------------------------------------------------------------|
| 2    | u16    | The procedure number; with bit 15 (0x8000) set, the call picks the procedure of the game's language |
| ...  | values | The arguments                                                                                       |
| 1    | u8     | 00, the end of the call                                                                             |

### Blocks

A block holds its statements, then a 00 byte. The body of every procedure and main are blocks.

PS2 text encoding
-----------------

String resources use the text encoding of the PS2 releases. The listing writes them as markup that compiles back to
the same bytes.

| Bytes            | Meaning                                                          | Markup                                          |
|------------------|------------------------------------------------------------------|-------------------------------------------------|
| 20-7E but 7B, 7D | The ASCII character                                              | the character                                   |
| `0A`             | Line break                                                       | a line break (`\n` in the listing)              |
| 1F xx            | An accented Latin letter, from the table below                   | the letter                                      |
| L xx, L ≥ 80     | A two-byte code: bits 0-4 of L the page, bits 5 and 6 attributes | see below                                       |
| anything else    | No character, including `{` and `}`                              | its bytes in hex between braces, such as `{7B}` |

| Page | Lead without attributes | Characters                                                                            |
|------|-------------------------|---------------------------------------------------------------------------------------|
| 0    | 80                      | ASCII; written as a character only with an attribute, else `{80xx}`                   |
| 1    | 81                      | Hiragana: code n is U+3040 + n for 01 to 4F; 50 is U+3092, 51 is U+3093               |
| 2    | 82                      | Katakana: code n is U+30A0 + n for 01 to 4F; 50 is U+30F2, 51 is U+30F3, 52 is U+30F4 |
| 3    | 83                      | Symbols, from the table below                                                         |
| 12   | 8C                      | Glyphs 1 to 255 of the script: 8C 01 to 8C FF                                         |
| 13   | 8D                      | Glyphs 256 to 510: 8D 01 to 8D FF                                                     |

Bit 6 (0x40) of the lead byte is written as U+E000 and bit 5 (0x20) as U+E001 before the character, as the Bluepoint
texts write them: C0 41 is `\uE000A` in the listing, A1 22 is U+E001 followed by U+3062. MGTools does not decode what
the attributes do. A `{` right after an attribute character is the brace itself, not the start of a hex code.
Glyph codes and other codes without a character are always written in hex, such as `{8C01}`.

Accented letters (1F xx):

| xx | Letter | xx | Letter | xx | Letter | xx | Letter | xx | Letter |
|----|--------|----|--------|----|--------|----|--------|----|--------|
| 04 | É      | 0B | ä      | 14 | ì      | 1B | ö      | 3D | º      |
| 06 | Ö      | 0E | ç      | 15 | î      | 1D | ú      | 41 | ¿      |
| 07 | Ü      | 0F | é      | 17 | ñ      | 1F | û      | 42 | ¡      |
| 08 | á      | 10 | è      | 18 | ó      | 20 | ü      | 64 | „      |
| 09 | à      | 11 | ê      | 19 | ò      | 28 | ß      | 6B | Í      |
| 0A | â      | 13 | í      | 1A | ô      | 3C | ª      |    |        |

Symbols (83 xx):

| xx | Character      | xx | Character  |
|----|----------------|----|------------|
| 01 | U+3000 (space) | 08 | U+3001 (、) |
| 02 | U+E081         | 09 | U+3002 (。) |
| 03 | U+E083         | 0B | U+300F (』) |
| 04 | U+E082         | 12 | U+30FC (ー) |
| 05 | U+E080         | 17 | U+300E (『) |
| 07 | U+FF1F (？)     |    |            |

U+E080 to U+E083 are private-use characters, which the listing writes as `\uE080` and so on. Accented letters take no
attributes; MGTools refuses such a combination, a character the encoding lacks and markup that ends with an attribute.
When compiling, it also refuses a string that uses a glyph beyond the number of glyphs the listing declares.

Name hash (strcode)
-------------------

The engine names commands and other things by a 24-bit hash of their ASCII name, the strcode:

```text
code = 0
for each byte b of the name:
    code = ((code >> 19) | (code << 5)) & 0xFFFFFF    # rotate 24 bits left by 5
    code = (code + b) & 0xFFFFFF
if code == 0: code = 1
```

| Name        | Strcode  |
|-------------|----------|
| `if`        | 0x000D86 |
| `print`     | 0x3AB23B |
| `switch`    | 0xA65DB5 |
| `door`      | 0x33CA52 |
| `open_door` | 0x966474 |

The steps for `door` are 0x64 (`d`), 0xCEF (`o`), 0x19E4F (`o`) and 0x33CA52 (`r`). In `open_door`, the fifth letter
is the first where the rotation carries bits from the top to the bottom: 0x394D0E rotates to 0x29A1C7, and adding `_`
(0x5F) gives 0x29A226.

[2D layouts](la2.md) and [sprite atlases](tri.md) name things by strcodes too.

A listing writes a name as such when MGTools knows it or a [dictionary](#strcode-dictionaries) gives it, else as `#`
and six hex digits. It knows the commands `chara`, `command`, `if`, `load`, `print`, `return` and `switch`, the names
`ending`, `init`, `scenerio` and `varsave`, and the stage names that key the table of location names (such as `s001a`).
A listing may use any name: the compiler hashes it, so `lamp` compiles to the strcode the listing later shows as
`#379210`.

### Strcode dictionaries

`mgtools gcx export --dictionary` reads a text file that names more strcodes. Each line holds a strcode in hex
(`379210`, `0x379210` or `#379210`), whitespace and a name. Words after the name, such as a comment column, are
ignored, since a name holds no whitespace; blank lines are skipped:

```text
379210 lamp
966474 open_door  // a comment
```

The listing writes these names in place of `#` and the hex digits, and in place of a built-in name of the same strcode.
The compiler hashes the names back, so export uses only the lines whose name compiles back to its strcode and skips
lines such as these:

| Skipped line                                                             | Example                                    |
|--------------------------------------------------------------------------|--------------------------------------------|
| Fewer words than a strcode and a name                                    | `379210`                                   |
| A strcode that is not one to six hex digits, such as a header            | `37921G lamp`, `strcode name`              |
| A name that is not ASCII letters, digits and `_`, or starts with a digit | `379210 9lamp`, `379210 ランプ`               |
| A name that hashes to another strcode                                    | `379210 lamq` (`lamq` hashes to `#379211`) |
| A second name for a strcode, after its first                             | `000D86 jF` after `000D86 if`              |

The listing writes the strcode of a skipped line as it does without the dictionary, so the script still compiles back
byte for byte. Export prints one warning for a dictionary with skipped lines: their number, and the line number and
reason of the first three, enough to tell a header, comments and typos apart without listing a whole file:

```text
Warning: names.txt: skipped 4 lines that a listing cannot use:
  Line 1: 'strcode' is not a strcode of up to six hex digits
  Line 3: open_dor hashes to #14B323, not #966474
  Line 5: #000D86 already has the name if
  and 1 more
```

The file is read as UTF-8, with or without a byte order mark, or else as EUC-JP, and export refuses a file that is
neither. Names are ASCII in both, so the encoding only changes how a skipped line shows.

Editable form
-------------

`mgtools gcx export` writes a folder named after the file:

| Path         | Contents                                                                                                                                                                 |
|--------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `script.gcl` | The listing: the variant, timestamp, seed (plain files), number of glyphs, code and resources                                                                            |
| `text.xlf`   | Bluepoint files: the UTF-8 text of each string resource as unit `res:N`, with the PS2 markup as a note where it differs (`text.xliff` or `text.po` in the other formats) |
| `glyphs.png` | Scripts with glyphs: the glyphs, 24 × 24 pixels each, 16 a row, as an indexed image whose values 0 to 3 show as the greys 0, 85, 170 and 255                             |

`mgtools gcx import` reads the folder back. The translation document must hold a unit for each string resource and no
other units; `glyphs.png` must have the size the number of glyphs gives, and its pixels must be palette indices 0 to 3
or one of the four greys, a fully transparent pixel counting as 0.

### Listing

```text
gcx bluepoint | plain
timestamp 0x<u32>
seed 0x<u32>               (plain files only)
glyphs <0 to 510>

proc <number> [lang 0x<language>] { <statement>; ... }
main { <statement>; ... }

string "<markup>"          // res:0
data {<values>}            // res:1
```

Procedures appear in the order the file stores their bodies, and resources in their order; the comment after each
resource gives the number code refers to it by. Statements end with a semicolon, whitespace and `//` comments are free,
and numbers are decimal or `0x` hex. An expression statement that would start with a name is put in parentheses so
that it does not read as a command. Strings take the escapes `\\`, `\"`, `\n`, `\xHH` and `\uHHHH`; the listing writes
control and private-use characters as `\uHHHH`.

| Value               | Listing                                                                       |
|---------------------|-------------------------------------------------------------------------------|
| Integer             | `-5`, `300`, `0x12C`                                                          |
| Name                | `print`, `#3AB23B`                                                            |
| String in code      | `"Hello"`                                                                     |
| Procedure reference | `&2`                                                                          |
| Resource reference  | `res:3`                                                                       |
| Symbol              | `t:0x0000002A`                                                                |
| Argument            | `$arg0` to `$arg14`                                                           |
| Variable            | `$` region letter, type letter, `[0xOOOO]`; flags add `.bit`: `$gf[0x0004.3]` |
| Element             | `$li[0x0100:4][$arg1]`: offset, array size, index                             |
| Expression          | `(...)`; unary operators need parentheses: `-(x)`, `!(x)`, `~(x)`             |
| Block               | `{ statement; ... }`                                                          |

| Statement  | Listing                                       |
|------------|-----------------------------------------------|
| Command    | `name values -letter values ...`              |
| Call       | `@number values`, `@0x8001 values` for bit 15 |
| Expression | `$gw[0x0010] = 3`                             |

Worked example
--------------

An invented Bluepoint script with one procedure that prints resource 0, a main that sets a variable and calls the
procedure, a string and a list of values. Its listing:

```text
gcx bluepoint
timestamp 0x5F000000
glyphs 0

proc 1 {
    print res:0;
}

main {
    $gw[0x0010] = 3;
    @1;
}

string "DOOR"  // res:0
data {5 #33CA52}  // res:1
```

and `text.xlf` gives res:0 the UTF-8 text `Door`. The file, 0x74 bytes:

```text
0000  4C 43 47 42 00 00 00 5F 00 00 00 00 FF FF FF FF
0010  41 00 00 00 29 00 00 00 31 00 00 00 3D 00 00 00
0020  00 00 00 00 18 00 00 00 02 00 00 00 0C 00 00 00
0030  FF FF FF FF 44 6F 6F 72 00 00 00 00 80 05 00 00
0040  00 44 4F 4F 52 00 C6 06 52 CA 33 00 46 04 00 00
0050  00 0B 00 00 00 8A 68 3B B2 3A 03 0E 00 00 00 00
0060  0F 00 00 00 8D 0D 37 11 00 00 10 C4 B6 A0 73 01
0070  00 00 00 00
```

| Offset | Bytes                        | Meaning                                                                         |
|--------|------------------------------|---------------------------------------------------------------------------------|
| 0x00   | `4C 43 47 42`                | `LCGB`                                                                          |
| 0x04   | `00 00 00 5F`                | Timestamp 0x5F000000                                                            |
| 0x08   | `00 00 00 00`                | Procedure 1: language 0, body at 0                                              |
| 0x0C   | `FF FF FF FF`                | End of the procedure table; B = 0x10                                            |
| 0x10   | `41 00 00 00`                | Code at B + 0x41 = 0x51                                                         |
| 0x14   | `29 00 00 00`                | Resource table at B + 0x29 = 0x39                                               |
| 0x18   | `31 00 00 00`                | Resource area at B + 0x31 = 0x41                                                |
| 0x1C   | `3D 00 00 00`                | Glyphs at B + 0x3D = 0x4D                                                       |
| 0x20   | `00 00 00 00`                | Seed 0                                                                          |
| 0x24   | `18 00 00 00`                | Size of the Bluepoint header                                                    |
| 0x28   | `02 00 00 00`                | Two resources                                                                   |
| 0x2C   | `0C 00 00 00`                | Text of res:0 at 0x28 + 0x0C = 0x34                                             |
| 0x30   | `FF FF FF FF`                | res:1 has no text                                                               |
| 0x34   | `44 6F 6F 72 00`             | `Door`                                                                          |
| 0x39   | `00 00 00 80`                | res:0: a string at 0                                                            |
| 0x3D   | `05 00 00 00`                | res:1: a list of values at 5                                                    |
| 0x41   | `44 4F 4F 52 00`             | `DOOR` in the PS2 encoding                                                      |
| 0x46   | `C6 06 52 CA 33 00`          | 5, the strcode 0x33CA52, end of the list                                        |
| 0x4C   | `46`                         | Padding: `F`                                                                    |
| 0x4D   | `04 00 00 00`                | Glyph section of 4 bytes: no glyphs                                             |
| 0x51   | `0B 00 00 00`                | The procedure bodies take 11 bytes                                              |
| 0x55   | `8A`                         | Block of 10 bytes                                                               |
| 0x56   | `68 3B B2 3A 03 0E 00 00 00` | Command of 8 bytes: `print` (3AB23B), 3 bytes of arguments: `res:0`, no options |
| 0x5F   | `00`                         | End of the block                                                                |
| 0x60   | `0F 00 00 00`                | Main takes 15 bytes                                                             |
| 0x64   | `8D 0D`                      | Block of 13 bytes, the size in the next byte                                    |
| 0x66   | `37 11 00 00 10 C4 B6 A0`    | Expression of 7 bytes: short global 0x0010, 3, assign, end                      |
| 0x6E   | `73 01 00 00`                | Call of 3 bytes: procedure 1, no arguments, end                                 |
| 0x72   | `00`                         | End of the block                                                                |
| 0x73   | `00`                         | Padding to 4 bytes                                                              |

The same script as a plain file with the seed 0x12345678 has a 0x14-byte header, no texts, and an encrypted area:

```text
0000  00 00 00 5F 00 00 00 00 FF FF FF FF 2C 00 00 00
0010  14 00 00 00 1C 00 00 00 28 00 00 00 78 56 34 12
0020  00 00 00 80 05 00 00 00 7D FD 3F 02 BE BB C8 10
0030  B5 25 CA F8 00 00 00 00 0B 00 00 00 8A 68 3B B2
0040  3A 03 0E 00 00 00 00 0F 00 00 00 8D 0D 37 11 00
0050  00 10 C4 B6 A0 73 01 00 00 00 00 00 00 00 00 00
```

The first state is 0x12345678 × 0x7D2B89DD + 0xCF9 = 0xD79CEA91 (mod 2^32), whose bits 15-22 are 0x39. The keystream
`39 B2 70 50 BE 7D CE 42 7F 16 CA BE` XORed with the area `44 4F 4F 52 00 C6 06 52 CA 33 00 46` gives the stored bytes
at 0x28. The glyph section is the u32 0 at 0x34, and zeros pad the file from 0x5A to 0x60.

More statements, with their bytes:

| Listing                                                      | Bytes                                                                                    |
|--------------------------------------------------------------|------------------------------------------------------------------------------------------|
| `print "Hello" $arg0;`                                       | `6D 0E 3B B2 3A 09 07 06 48 65 6C 6C 6F 00 40 00`                                        |
| `#379210 300 -x &1 t:0x0000002A;`                            | `6D 12 10 92 37 03 01 2C 01 59 78 08 01 00 0A 2A 00 00 00 00`                            |
| `if ($gf[0x0004.3] && $lb[0x0002] < 10) { @0x8001 res:0; };` | `6D 1B 86 0D 00 16 3C 14 03 00 04 12 10 00 02 CB AD B5 A0 88 76 01 80 0E 00 00 00 00 00` |
| `$li[0x0100:4][$arg1] = -(70000);`                           | `3D 0F 29 10 01 00 C5 41 C1 09 70 11 01 00 A1 B6 A0`                                     |

In the third, the command `if` (000D86) has 0x16 bytes of arguments: an expression of 12 bytes (flag global 0x0004 bit
3, byte local 0x0002, 10, less, logical and, end) and a block of 8 bytes holding a call of procedure 0x8001 with the
argument `res:0`. In the fourth, the unary negate takes the placeholder 0 (C1) and 70000 (09 70 11 01 00) before its
operator A1. The string resource `"\uE000A{8C01}\n"` is C0 41 8C 01 0A.
