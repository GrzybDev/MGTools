# Console font

The console font, `EngineSupport/Fonts/console.cfon`, maps characters to glyphs: a glyph is a box in a texture, and
each character, from the ASCII codes up to four-byte UTF-8 sequences, names the glyph it is drawn with. The texture
is `EngineSupport/Fonts/_win/console.ctxr`, the only [texture](ctxr.md) of version 5. `mgtools cfon export` writes
the boxes and the glyph of each character as JSON, and `mgtools cfon import` builds the font back (see
[Usage](../README.md#console-font)).

Overall layout
--------------

Every number is big-endian. The file is neither compressed nor encrypted, and its parts follow each other without
padding:

| Offset | Size        | Type    | Description                                                           |
|--------|-------------|---------|-----------------------------------------------------------------------|
| 0x00   | 4           | char[4] | Magic `FONT`                                                          |
| 0x04   | 4           | u32     | 5                                                                     |
| 0x08   | 4           | u32     | 10                                                                    |
| 0x0C   | 4           | u32     | 2                                                                     |
| 0x10   | 4           | u32     | 0x41500000, which reads 13.0 as a float32                             |
| 0x14   | 4           | u32     | Number of floats in the boxes: 4 × glyph count                        |
| 0x18   | 16 × glyphs | f32[4]  | The box of each glyph: u0, v0, u1, v1, from 0 to 1 across the texture |
| -      | -           | -       | Nine arrays (below)                                                   |
| -      | 1           | u8      | Length of the texture's path                                          |
| -      | length      | char[]  | The texture's path, in ASCII                                          |

MGTools takes the 16 bytes from 0x04 as part of the magic and requires them as they are; their meaning is not known.

Arrays
------

Each array is a u32 count followed by its values:

| Array | Type | Count       | Values                                                   |
|-------|------|-------------|----------------------------------------------------------|
| 1     | u16  | Glyph count | 0 per glyph, whose meaning is not known                  |
| 2     | u16  | 128         | The glyph of each ASCII code, from 0x00 to 0x7F          |
| 3     | u16  | n2          | The glyphs of the characters of two-byte UTF-8 sequences |
| 4     | u16  | n2          | Their keys                                               |
| 5     | u16  | n3          | The glyphs of the characters of three-byte sequences     |
| 6     | u32  | n3          | Their keys                                               |
| 7     | u16  | n4          | The glyphs of the characters of four-byte sequences      |
| 8     | u32  | n4          | Their keys                                               |
| 9     | u16  | 128         | 1 per ASCII code, whose meaning is not known             |

A glyph is the index of a box, from 0. A key is a character's UTF-8 sequence read as a big-endian number: `é` is
`C3 A9`, the key 0xC3A9, and `€` is `E2 82 AC`, the key 0x00E282AC. Keys are sorted in ascending order, and the
glyph at a position of its array belongs to the key at the same position.

Editable form
-------------

Export writes JSON with these keys:

| Key          | Description                                                      |
|--------------|------------------------------------------------------------------|
| `texture`    | The texture's path                                               |
| `glyphs`     | The boxes, each a list of `u0`, `v0`, `u1` and `v1`              |
| `characters` | Each character with the index of its glyph, sorted by code point |

Import sorts the characters by the length of their UTF-8 sequence and by key, and writes the arrays and their
counts. To give a character a glyph of its own, draw it in the texture with [`mgtools ctxr`](ctxr.md), add its box
to `glyphs` and map the character to the new index.

Checks and refusals
-------------------

Export refuses a file that does not start with the 20 bytes of the header ("Not a console font of the Master
Collection"), a key that is not a UTF-8 sequence of its array's length, and a file that holds anything MGTools
would write otherwise, such as other values in arrays 1 and 9, keys out of order or data after the
path. The message names the offset of the first such byte.

Import refuses a font in which an ASCII character, U+0000 to U+007F included, has no glyph, a key that is not one
character, a glyph index that is not a box of the font, and a texture path that is not ASCII or longer than 255
bytes. The messages name the JSON file.

Worked example
--------------

An invented font of three boxes in a texture `fonts/example.ctxr`: every ASCII code uses box 0 except `A`, which uses
box 1; `é` and `€` use box 2, and the four-byte character U+1D11E uses box 1. The file is 661 bytes long:

```text
0000  46 4F 4E 54 00 00 00 05 00 00 00 0A 00 00 00 02
0010  41 50 00 00 00 00 00 0C 00 00 00 00 00 00 00 00
0020  3D 80 00 00 3E 00 00 00 3D 80 00 00 00 00 00 00
0030  3E 00 00 00 3E 00 00 00 3E 00 00 00 00 00 00 00
0040  3E 40 00 00 3E 00 00 00
```

- 0x00: the magic and the constant words; 0x14: 12 floats for 3 boxes.
- 0x18: box 0 is 0, 0, 0.0625, 0.125; box 1 is 0.0625, 0, 0.125, 0.125; box 2 is 0.125, 0, 0.1875, 0.125.

The arrays follow:

| Offset | Array | Bytes                                 | Values                                                      |
|--------|-------|---------------------------------------|-------------------------------------------------------------|
| 0x48   | 1     | `00 00 00 03 00 00 00 00 00 00`       | 3 words of 0                                                |
| 0x52   | 2     | `00 00 00 80`, then 128 u16           | Box 0 for every code; 0xD8 holds 1, the glyph of `A` (0x41) |
| 0x156  | 3     | `00 00 00 01 00 02`                   | One two-byte character, box 2                               |
| 0x15C  | 4     | `00 00 00 01 C3 A9`                   | Its key, `é`                                                |
| 0x162  | 5     | `00 00 00 01 00 02`                   | One three-byte character, box 2                             |
| 0x168  | 6     | `00 00 00 01 00 E2 82 AC`             | Its key, `€`                                                |
| 0x170  | 7     | `00 00 00 01 00 01`                   | One four-byte character, box 1                              |
| 0x176  | 8     | `00 00 00 01 F0 9D 84 9E`             | Its key, U+1D11E                                            |
| 0x17E  | 9     | `00 00 00 80`, then 128 times `00 01` | 1 per ASCII code                                            |
| 0x282  | -     | `12 66 6F 6E 74 73 2F ...`            | The path, 18 bytes: `fonts/example.ctxr`                    |

Export writes this JSON, shortened here where the ASCII characters follow each other; the file puts every value on a
line of its own:

```text
{
  "texture": "fonts/example.ctxr",
  "glyphs": [
    [0.0, 0.0, 0.0625, 0.125],
    [0.0625, 0.0, 0.125, 0.125],
    [0.125, 0.0, 0.1875, 0.125]
  ],
  "characters": {
    "\u0000": 0,
    "\u0001": 0,
    ...
    "@": 0,
    "A": 1,
    "B": 0,
    ...
    "~": 0,
    ...
    "é": 2,
    "€": 2,
    "𝄞": 1
  }
}
```
