# MSX fonts

The font of the [MSX resource files](msx-resource.md): section 75 in Metal Gear and section 48 in Metal Gear 2: Solid
Snake. `mgtools resource export` writes it as PNG images and `font.json`, and `mgtools resource import` builds it back
(see [Usage](../README.md#resource-files)).

Pages
-----

The font section is a container of five leaves, the pages; MGTools refuses another number.

| Page | Kind         | Glyph height | Codes            |
|------|--------------|--------------|------------------|
| 0    | Proportional | 24           | `20` to `FF`     |
| 1    | Proportional | 12           | `20` to `FF`     |
| 2    | Proportional | 18           | `20` to `FF`     |
| 3    | Proportional | 24           | `20` to `FF`     |
| 4    | Double-byte  | 24, 24 wide  | `8000` to `FFFF` |

Import checks every [text](msx-text.md) against page 0, for its single bytes, and page 4, for its double-byte
characters. A proportional glyph is 1 to 64 pixels wide.

Proportional pages
------------------

A proportional page starts with a table of 4-byte little-endian slots, one for each code from `1E` to `FF`, followed by
the glyphs:

| Offset    | Size | Type        | Description                                           |
|-----------|------|-------------|-------------------------------------------------------|
| 0x000     | 4    | u32 LE      | Slot `1E`: first header word                          |
| 0x004     | 4    | u32 LE      | Slot `1F`: second header word                         |
| 0x008     | 896  | u32 LE[224] | Slots of codes `20` to `FF`; code c at (c − 0x1E) × 4 |
| 0x388     | n    | bytes       | Glyph data, in code order                             |
| 0x388 + n | ...  | zero bytes  | Legacy pages only: padding to 20,480 bytes            |

### Header

Slots `1E` and `1F` tell the two kinds of page apart:

| Kind   | Slot `1E`        | Slot `1F`              | Page size                               |
|--------|------------------|------------------------|-----------------------------------------|
| Legacy | 0                | 0                      | 20,480 bytes, zeros after the glyphs    |
| Sized  | v << 24 \| 0x388 | The page size in bytes | The table and the glyphs, nothing after |

v is a constant of the page, from 0 to 255. MGTools refuses any other header, a legacy page of another size, non-zero
bytes after the glyphs of a legacy page and any bytes after those of a sized page.

### Slots

A code with a glyph has this slot:

| Bits  | Description                                           |
|-------|-------------------------------------------------------|
| 0-19  | Offset of the glyph from the end of the table (0x388) |
| 20-25 | Width minus 1                                         |
| 26-31 | v >> 2 on a sized page, 0 on a legacy page            |

A code without a glyph has `FFF0` in bits 16-31 and, in bits 0-15, the offset where the next glyph starts. The glyphs
follow each other in code order with no gaps, so every slot holds the size of all the glyphs of lower codes. MGTools
refuses a slot whose offset is any other, or whose bits 26-31 differ from those of its page.

### Glyphs

A glyph has `width` × `height` pixels of 2 bits, row by row from the top, four to a byte with the first pixel in the
two highest bits and no padding between rows. The pixels take the values 0 to 3.

A glyph takes ceil(width × height / 4) bytes. On a floor-packed page, glyphs round down instead and take
floor(width × height / 4) bytes; the engine draws the last two pixels of such a glyph from the first bits of the next
one. The two packings differ only where width × height is not a multiple of 4, which among the page heights happens on
page 2 with an odd width. A page packs all its glyphs one way; MGTools refuses a page that mixes them. The bits after
the last pixel of a ceiling-packed glyph may be non-zero, and MGTools keeps them.

The last slot, `FF`, has no next offset to give its size. On a sized page its glyph ends where the page ends; on a
legacy page MGTools takes it as ceiling-packed.

The glyphs of a legacy page fit in 19,576 bytes, those of a sized page in 64,631 bytes, since its size and the offsets
of empty slots take 16 bits; import refuses more.

Page 4
------

Page 4 holds the glyphs of the double-byte characters, 24 × 24 pixels each, and maps the codes to them. Its values are
big-endian:

| Offset  | Size        | Type          | Description                                                              |
|---------|-------------|---------------|--------------------------------------------------------------------------|
| 0x00000 | 2           | u16 BE        | 0                                                                        |
| 0x00002 | 2           | u16 BE        | 144, the size of a glyph in bytes                                        |
| 0x00004 | 65,536      | u16 BE[32768] | Glyph of each code from `8000` to `FFFF`; code c at 4 + (c − 0x8000) × 2 |
| 0x10004 | 144 × count | bytes         | Glyphs, numbered from 0                                                  |

A glyph holds 576 pixels of 2 bits, packed as on the proportional pages. A code mapped to 0 draws glyph 0, so glyph 0
has no code of its own, and each other glyph is mapped by at most one code. MGTools refuses another header, a map
entry past the last glyph, two codes mapped to one glyph and bytes after the glyphs that make no whole glyph.

Version differences
-------------------

Only the Japanese release has sized pages. MGTools takes a font whose page 1 is sized for the Japanese one, which
picks the Japanese charmap, the Japanese line limits and the source language of the texts (see
[MSX texts](msx-text.md)). Otherwise it reads the font as European.

Editable form
-------------

`font/page0.png` to `font/page3.png` show the proportional pages. Each is 1,024 pixels wide, 16 cells of 64 pixels, and
14 rows of cells as high as the glyphs of the page. The cell of code c is in column (c − 0x20) mod 16 and row
(c − 0x20) div 16, and a glyph takes the first `width` columns of its cell. The images are indexed:

| Index | Colour                                     | Meaning                                   |
|-------|--------------------------------------------|-------------------------------------------|
| 0-3   | `#000000`, `#555555`, `#aaaaaa`, `#ffffff` | The pixel values 0 to 3                   |
| 4     | `#282870`                                  | The part of a glyph's cell past its width |
| 5     | `#702020`                                  | The cell of a code without a glyph        |

On a floor-packed page, the images show the pixels as the engine draws them, the last two taken from the next glyph.
`font/page4.png` shows the glyphs of page 4 in order, 32 cells of 24 pixels a row.

`font.json` holds the rest:

| Key           | Description                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------|
| `charmap`     | The character of each code from `7F` and `A0` to `DF` that has one (see [Charmaps](msx-text.md#charmaps))                       |
| `pages`       | Pages 0 to 3, each with `widths`, the width of each glyph by code (`"41": 7`), and as needed `floor_packed`, `v` and `pad_bits` |
| `double_byte` | The character each glyph of page 4 is mapped to, in order; `null` for a glyph without one                                       |

`pad_bits` gives, by code, the bits after the last pixel of a ceiling-packed glyph that are not zero. Export names
glyph 0, the first entry of `double_byte`, after the lowest double-byte code the texts use that no glyph maps; glyph 0
draws that code anyway, so the name writes nothing to the page.

Import reads the pixels of each glyph from the first `width` columns of its cell, which must be indices 0 to 3, one of
the four greys or transparent (read as 0). It refuses widths outside 1 to 64, codes outside `20` to `FF`, a `v` that is
not a byte, `pad_bits` on a floor-packed page, for a code without a glyph or past the room of its last byte,
characters listed twice or not double-byte in `double_byte`, and images of another size. On a floor-packed page, it
also refuses a glyph whose last two pixels differ from those the next glyph gives them; removing `floor_packed` keeps
them as drawn.

### Separate glyph images

With `--separate-glyphs`, export saves each glyph as its own PNG image instead of an image per page: the glyphs of
page N go to the folder `font/pageN/`. An image is as wide as its glyph and as high as the glyphs of its page, 24 × 24
pixels on page 4, indexed in the four greys of the values 0 to 3; on a floor-packed page it shows the pixels as the
engine draws them, as the page images do. A page without glyphs has no folder.

Each image is named after the character of its glyph where it has one:

| Glyph                                                                               | Image name               | Example                        |
|-------------------------------------------------------------------------------------|--------------------------|--------------------------------|
| A code of `20` to `7E`, a code the charmap names or a double-byte character         | `U+` and the code point  | `U+0041.png`, `U+3042.png`     |
| A single-byte code without a character, or a double-byte code read as `{sjis:HHHH}` | `code-` and the code     | `code-FF.png`, `code-818B.png` |
| Glyph 0 of page 4 without a character                                               | `fallback.png`           | `fallback.png`                 |
| Another glyph of page 4 that no code is mapped to                                   | `unused-` and its number | `unused-4.png`                 |

`font.json` records this form. Each page names its folder in `glyphs` and the image of each glyph, by code, in
`images`; `double_byte_glyphs` names the folder of page 4 and `double_byte_images` the image of each of its glyphs, in
the order of `double_byte`:

```json
{
  "glyphs": "font/page0",
  "widths": {"20": 4, "41": 7},
  "images": {"20": "U+0020.png", "41": "U+0041.png"}
}
```

Import reads each page in the form `font.json` gives it, and each image by the name `font.json` gives it, so an image
can be renamed along with its name there. A glyph added to pages 0 to 3 takes a width and an image by its code; one
added to page 4 takes its character in `double_byte` and its image in `double_byte_images`. Every check of the page
images applies, and import also refuses an image whose size is not that of its glyph, a code with a width but no image
or an image but no width, and a `double_byte_images` list of another length than `double_byte`.

Worked example
--------------

An invented legacy page 0 with two glyphs: a blank space of 2 × 24 pixels at code `20`, and a glyph of 3 × 24 pixels
at code `41` whose rows are the values 3, 2, 1.

| Offset | Slot      | Word       | Meaning                                    |
|--------|-----------|------------|--------------------------------------------|
| 0x000  | `1E`      | `00000000` | Legacy header                              |
| 0x004  | `1F`      | `00000000` | Legacy header                              |
| 0x008  | `20`      | `00100000` | Offset 0, width 2                          |
| 0x00C  | `21`-`40` | `FFF0000C` | No glyph; the next glyph starts at 12      |
| 0x08C  | `41`      | `0020000C` | Offset 12, width 3                         |
| 0x090  | `42`-`FF` | `FFF0001E` | No glyph; the next glyph would start at 30 |

The glyph data starts at 0x388: 12 zero bytes for the space (48 pixels), then 18 bytes for `41` (72 pixels). Zeros pad
the page to 20,480 bytes.

```text
00388  00 00 00 00 00 00 00 00 00 00 00 00 E7 9E 79 E7
00398  9E 79 E7 9E 79 E7 9E 79 E7 9E 79 E7 9E 79 00 00
```

`E7` is `11 10 01 11` in bits: the first row 3, 2, 1, then the first pixel of the second row, 3.

An invented sized page 1 with v = 12 and one glyph of 5 × 12 pixels at code `42` takes 919 bytes:

| Offset | Slot      | Word       | Meaning                                     |
|--------|-----------|------------|---------------------------------------------|
| 0x000  | `1E`      | `0C000388` | v = 12, table of 0x388 bytes                |
| 0x004  | `1F`      | `00000397` | Page size, 919 bytes                        |
| 0x008  | `20`-`41` | `FFF00000` | No glyph; the next glyph starts at 0        |
| 0x090  | `42`      | `0C400000` | Bits 26-31 = 3 (12 >> 2), width 5, offset 0 |
| 0x094  | `43`-`FF` | `FFF0000F` | No glyph; 15 bytes of glyphs before         |

On an invented floor-packed page 2, two glyphs of 3 × 18 pixels (54 pixels, 13.5 bytes) at `41` and `42` take 13 bytes
each: their slots are `00200000` and `0020000D`, and slot `43` is `FFF0001A`. Ceiling-packed, the first would take 14
bytes.

An invented page 4 with glyph 1 mapped to `82A0` (`あ`) starts `00 00 00 90`, holds `00 01` at offset 0x00544 and takes
65,828 bytes: the 65,540 bytes of the header and the map, then glyph 0 at 0x10004 and glyph 1 at 0x10094.
