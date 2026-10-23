# TNOF fonts

A TNOF font holds the glyphs the Master Collection engine draws UTF-8 text with, such as the texts of
[GCX scripts](gcx.md) and [string tables](stov.md): per code point, its metrics and an 8-bit coverage value per
pixel. `mgtools tnof export` writes a font as `font.json` and a greyscale PNG image per glyph, and
`mgtools tnof import` builds it back (see [Usage](../README.md#tnof-fonts)).

The install holds `EngineSupport/Fonts/MGS_Font.raw`, but it does not appear to be used: the engine draws with a TNOF
font built into `METAL GEAR.exe` (see [The built-in font](#the-built-in-font)).

Overall layout
--------------

Every number is little-endian. The file is neither compressed nor encrypted.

| Offset           | Size      | Type    | Description                                            |
|------------------|-----------|---------|--------------------------------------------------------|
| 0x00             | 4         | char[4] | Magic `TNOF`                                           |
| 0x04             | 4         | u32     | A word whose meaning is not known                      |
| 0x08             | 4         | u32     | A word whose meaning is not known                      |
| 0x0C             | 4         | u32     | A word whose meaning is not known                      |
| 0x10             | 4         | u32     | Offset of the table: 0x18                              |
| 0x14             | 4         | u32     | Entry count                                            |
| 0x18             | 8 × count | -       | The table                                              |
| 0x18 + 8 × count | -         | -       | The glyph records, one per entry, in the table's order |

A table entry:

| Offset | Size | Type | Description                             |
|--------|------|------|-----------------------------------------|
| +0x00  | 4    | u32  | Code point                              |
| +0x04  | 4    | u32  | Offset of the glyph record drawn for it |

The entries are sorted by code point.

A glyph record:

| Offset | Size           | Type | Description                                       |
|--------|----------------|------|---------------------------------------------------|
| +0x00  | 1              | u8   | Width in pixels                                   |
| +0x01  | 1              | u8   | Height in pixels                                  |
| +0x02  | 1              | s8   | Bearing x                                         |
| +0x03  | 1              | s8   | Bearing y                                         |
| +0x04  | 1              | u8   | Advance                                           |
| +0x05  | width × height | u8[] | Coverage, from 0 (none) to 255 (full), row by row |

The records follow each other without padding, and nothing follows the last one. A glyph without pixels, such as a
space, is 0 wide or 0 high and takes 5 bytes.

### Repeated code points

A code point can have several records. Every entry of that code point then points at its last record, so the
earlier records are stored but never drawn. MGTools keeps them, so the file rebuilds byte for byte.

Editable form
-------------

Export writes into the folder:

| Path                        | Contents                                                                                     |
|-----------------------------|----------------------------------------------------------------------------------------------|
| `font.json`                 | `header`, the words at 0x04, 0x08 and 0x0C, and `glyphs`, a row per record                   |
| `glyphs/U+XXXX.png`         | The drawn record of each code point that has pixels                                          |
| `glyphs/U+XXXX.unusedN.png` | An earlier record of a repeated code point; N counts the records of that code point after it |

A row of `glyphs` holds `code`, written as `U+` and at least four hex digits, `bearing_x`, `bearing_y` and `advance`.
A record without pixels has no image, and its row also holds `width` and `height`.

The images are 8-bit greyscale, as large as the glyph, with the coverage as the grey: black is none, white is full.
Import takes the size of a glyph from its image, lays the image over black and converts it to greyscale, so a white
glyph drawn on transparency imports with the coverage it shows. It then sorts the glyphs by code point, keeping the
order of the records of a repeated code point. To add a glyph, add a row anywhere in `glyphs` and draw its image as
`glyphs/U+XXXX.png`.

Checks and refusals
-------------------

Export refuses a file that does not start with `TNOF`, whose table is not at 0x18, that ends inside a record or has
bytes after the last record, and one with an entry that does not point at the last record of its code point.

Import refuses a `code` not written as `U+` and 4 to 6 hex digits, a row that gives `width` and `height`, as a record
without an image does, with both above 0, a width, height or advance outside 0 to 255, and a bearing outside -128
to 127. The messages name `font.json` or the glyph's code point.

The built-in font
-----------------

The engine draws its UTF-8 texts with a TNOF font that `METAL GEAR.exe` carries as a gzip member, whose header names
the file `MGS_Font_nht.raw`. It is a different font from `EngineSupport/Fonts/MGS_Font.raw`. MGTools does not read or
patch executables, but the member decompresses to a TNOF font that `mgtools tnof export` reads; the opt-in tests on
the Steam install check that it rebuilds byte for byte. This Python code reads the executable without changing it
and writes the font to the current folder:

```python
import zlib
from pathlib import Path

exe = Path("path/to/MG and MG2/METAL GEAR.exe").read_bytes()
# The member's 10-byte gzip header comes right before the file name.
start = exe.index(b"MGS_Font_nht.raw\0") - 10
font = zlib.decompressobj(zlib.MAX_WBITS | 16).decompress(exe[start:])
Path("MGS_Font_nht.raw").write_bytes(font)
```

A font imported back from it cannot take its place without patching the executable.

Worked example
--------------

An invented font with the three header words 24, 24 and 3 and four records: a space, a comma, and two records of
the full stop, the first of which is never drawn.

| Record | Code point | Width × height | Bearings | Advance | Coverage      |
|--------|------------|----------------|----------|---------|---------------|
| 0      | U+0020     | 0 × 0          | 0, 0     | 6       | -             |
| 1      | U+002C     | 1 × 2          | -1, 1    | 3       | `FF 80`       |
| 2      | U+002E     | 1 × 1          | 0, 1     | 2       | `FF`          |
| 3      | U+002E     | 2 × 2          | 1, 2     | 4       | `80 FF FF 80` |

```text
0000  54 4E 4F 46 18 00 00 00 18 00 00 00 03 00 00 00
0010  18 00 00 00 04 00 00 00 20 00 00 00 38 00 00 00
0020  2C 00 00 00 3D 00 00 00 2E 00 00 00 4A 00 00 00
0030  2E 00 00 00 4A 00 00 00 00 00 00 00 06 01 02 FF
0040  01 03 FF 80 01 01 00 01 02 FF 02 02 01 02 04 80
0050  FF FF 80
```

- 0x00: the magic, the header words 24, 24 and 3, the table offset 0x18 and 4 entries.
- 0x18: U+0020 at 0x38 and U+002C at 0x3D; both entries of U+002E point at 0x4A, the last record of that code point.
- 0x38: the space, 5 bytes. 0x3D: the comma, its bearing x -1 stored as `FF`, then 2 coverage bytes.
- 0x44: the full stop that is never drawn. 0x4A: the full stop that is drawn. The file ends at 0x53.

Export writes `glyphs/U+002C.png`, `glyphs/U+002E.png` (record 3) and `glyphs/U+002E.unused1.png` (record 2), and
this `font.json`, shown here with each row on one line:

```json
{
  "header": [24, 24, 3],
  "glyphs": [
    {"code": "U+0020", "bearing_x": 0, "bearing_y": 0, "advance": 6, "width": 0, "height": 0},
    {"code": "U+002C", "bearing_x": -1, "bearing_y": 1, "advance": 3},
    {"code": "U+002E", "bearing_x": 0, "bearing_y": 1, "advance": 2},
    {"code": "U+002E", "bearing_x": 1, "bearing_y": 2, "advance": 4}
  ]
}
```
