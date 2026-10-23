# Keepfonts

A keepfont is a 2-bit font of the Master Collection: Latin glyphs 24 pixels high for the byte codes 0x20 to 0xFF in
the Mac OS Roman layout, then kana glyphs of 24 × 24 pixels. The European languages read
`assets/raw/us/keepfont_stage_r_sna01_r.raw`, and Japanese reads `assets/raw/us/keepfont.raw`, which has the same
layout. `mgtools keepfont export` writes a keepfont as `keepfont.json`, a PNG image per Latin glyph and one of the
kana, and `mgtools keepfont import` builds it back (see [Usage](../README.md#keepfonts)).

Overall layout
--------------

Every number is little-endian. The file is neither compressed nor encrypted.

| Offset    | Size             | Type | Description                                   |
|-----------|------------------|------|-----------------------------------------------|
| 0x00      | 2                | u16  | End of the glyph table: 8 + 4 × entry count   |
| 0x02      | 2                | u16  | A word whose meaning is not known             |
| 0x04      | 4                | u32  | End of the Latin glyphs, where the kana start |
| 0x08      | 4 × entry count  | -    | The glyph table, an entry per code from 0x20  |
| Table end | -                | -    | The Latin glyphs                              |
| Latin end | 144 × kana count | -    | The kana glyphs                               |
| -         | 0 to 15          | -    | Zeros up to a multiple of 16 bytes            |

The table has 1 to 224 entries: entry i is the glyph of the byte code 0x20 + i.

| Offset | Size | Type | Description                                   |
|--------|------|------|-----------------------------------------------|
| +0x00  | 2    | u16  | Offset of the glyph from the end of the table |
| +0x02  | 2    | u16  | Info: the glyph's width and flags             |

| Bits of the info | Mask     | Meaning                                            |
|------------------|----------|----------------------------------------------------|
| 4 to 9           | `0x03F0` | Width minus 1: widths go from 1 to 64 pixels       |
| 11               | `0x0800` | Marks a glyph with a descender                     |
| Others           | -        | Flags whose meaning is not known, kept as they are |

Pixels
------

Every glyph is a stream of 2-bit pixels, values 0 to 3: four pixels per byte, the first in the two highest bits, row
after row with no padding between rows. A Latin glyph is 24 rows of its width, 6 × width bytes; a kana glyph is 24
rows of 24 pixels, 144 bytes.

The first Latin glyph starts at the end of the table, and each glyph starts at or after the end of the one before.
Bytes between the end of a glyph and the start of the next, or the Latin end, belong to no glyph; MGTools keeps
them with the glyph before them. The kana fill the file from the Latin end, as many as fit before the padding.

As the offsets are 16-bit, every Latin glyph has to start within 65535 bytes of the end of the table.

Editable form
-------------

Export writes into the folder:

| Path            | Contents                                                                                                                                                                                                           |
|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `keepfont.json` | `header`, the word at 0x02, and `latin`, a row per code in order: `code` (such as `0x20`), `flags` (the info without the width bits), and `unused`, the hex of the bytes that follow the glyph, when there are any |
| `latin/XX.png`  | The Latin glyph of code `XX` (two upper-case hex digits), as wide as the glyph and 24 pixels high                                                                                                                  |
| `kana.png`      | The kana, 24 pixels wide, one below the other                                                                                                                                                                      |

The images are indexed, with the four values shown as the greys 0, 85, 170 and 255. Import takes the indices of an
indexed image as they are, so they have to stay from 0 to 3. In an RGB or RGBA image, every pixel has to be one of
the four greys, fully opaque, or fully transparent, which reads as 0. The width of a Latin image gives the glyph's
width.

Checks and refusals
-------------------

Export refuses a file whose table does not end at 8 + 4 × n for an n from 1 to 224, a glyph that starts before the
end of the one before it (or, for the first, anywhere but the end of the table), Latin glyphs that run past the Latin
end, and a file that does not end with the zeros that pad the kana to a multiple of 16 bytes.

Import refuses:

- a `latin` row out of order (each `code` has to be the next one from 0x20) or past 0xFF;
- a `header` or `flags` that is not a 16-bit integer, and flags that use the width bits `0x03F0`;
- a Latin image that is not 24 pixels high or is wider than 64 pixels;
- a `kana.png` that is not 24 pixels wide or not a multiple of 24 pixels high;
- a pixel that is not one of the four values;
- a glyph that would start more than 65535 bytes after the end of the table: some glyphs need to be narrower.

The messages name the JSON file, the image or the code of the glyph.

Worked example
--------------

An invented keepfont with the header word 0x0100, two Latin glyphs and one kana glyph:

- 0x20, 3 pixels wide, all 0.
- 0x21, 1 pixel wide: rows 0 to 3 are 0, rows 4 to 15 are 3, row 16 is 1, rows 17 and 18 are 0, rows 19 and 20 are
  3, and rows 21 to 23 are 0.
- A kana glyph whose first and last rows are 2 and whose other rows are 0.

```text
0000  10 00 00 01 28 00 00 00 00 00 20 00 12 00 00 00
0010  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
0020  00 00 00 FF FF FF 43 C0 AA AA AA AA AA AA 00 00
0030  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
*
00B0  00 00 AA AA AA AA AA AA 00 00 00 00 00 00 00 00
00C0
```

- 0x00: the table ends at 0x10 (two entries), the header word 0x0100, and the Latin glyphs end at 0x28.
- 0x08: 0x20 at offset 0 with the info 0x0020, the width 3 minus 1 in bits 4 to 9; 0x21 at offset 0x12 with the info
  0, width 1.
- 0x10: the 18 bytes of 0x20.
- 0x22: the 6 bytes of 0x21. `00` holds rows 0 to 3, each `FF` four rows of 3, `43` (binary 01 00 00 11) rows 16 to
  19 and `C0` (11 00 00 00) rows 20 to 23.
- 0x28: the kana glyph, 144 bytes, its first row `AA` six times (pixels of 2), its last row at 0xB2.
- 0xB8: 8 zero bytes up to 0xC0, a multiple of 16.

Export writes `latin/20.png` (3 × 24 pixels), `latin/21.png` (1 × 24), `kana.png` (24 × 24) and:

```json
{
  "header": 256,
  "latin": [
    {
      "code": "0x20",
      "flags": 0
    },
    {
      "code": "0x21",
      "flags": 0
    }
  ]
}
```

Drawing `latin/21.png` 2 pixels wide instead makes the glyph of 0x21 2 pixels wide on import: its info becomes
0x0010, the Latin glyphs end 6 bytes later, and the kana move with them.
