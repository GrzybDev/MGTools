# Sprite atlases

A `.tri` file is a PS2 sprite atlas: for each sprite, the GS registers that cut it from a texture page. The Master
Collection draws each sprite from the HD texture its strcode names, so the GS memory the file reserves for the pages
and their palettes holds only zeros. `mgtools tri export` writes the sprites and their registers as JSON, and
`mgtools tri import` builds the atlas back, deriving each sprite's texture coordinates from its registers (see
[Usage](../README.md#sprite-atlases)).

The atlases sit in `assets/tri/us/*.tri` and in the folders of the other languages under `assets/tri/`.

Overall layout
--------------

Every number is little-endian. The file has no magic number and is neither compressed nor encrypted.

| Offset         | Size               | Contents                                                |
|----------------|--------------------|---------------------------------------------------------|
| 0x00           | 32                 | Header                                                  |
| 0x20           | 192 × sprite count | Sprite entries                                          |
| -              | -                  | Zeros up to the image offset, the next multiple of 0x80 |
| Image offset   | 256 × image rows   | GS memory for the texture pages, all zeros              |
| Palette offset | 256 × palette rows | GS memory for the palettes, all zeros                   |

Header
------

| Offset | Size | Type | Description                                                               |
|--------|------|------|---------------------------------------------------------------------------|
| 0x00   | 4    | u32  | 0                                                                         |
| 0x04   | 4    | u32  | Image rows: the 256-byte rows of GS memory the texture pages take         |
| 0x08   | 4    | u32  | Image rows again                                                          |
| 0x0C   | 4    | u32  | Palette rows: the 256-byte rows of GS memory the palettes take            |
| 0x10   | 4    | u32  | Sprite count                                                              |
| 0x14   | 4    | u32  | A word whose meaning is not known                                         |
| 0x18   | 4    | u32  | Image offset: 0x20 + 192 × sprite count, rounded up to a multiple of 0x80 |
| 0x1C   | 4    | u32  | Palette offset: image offset + 256 × image rows                           |

The file ends at the palette offset + 256 × palette rows. With no magic number, this is how MGTools tells an atlas
from other files.

Sprite entry
------------

| Offset | Size | Type   | Description                                                         |
|--------|------|--------|---------------------------------------------------------------------|
| +0x00  | 4    | f32    | u: where the sprite starts across its page, from 0 to 1             |
| +0x04  | 4    | f32    | v: where the sprite starts down its page                            |
| +0x08  | 4    | f32    | Width, as a fraction of the page                                    |
| +0x0C  | 4    | f32    | Height, as a fraction of the page                                   |
| +0x10  | 4    | u32    | Strcode of the sprite's HD texture                                  |
| +0x14  | 4    | u32    | 0                                                                   |
| +0x18  | 4    | u32    | A flag whose meaning is not known                                   |
| +0x1C  | 2    | u16    | TBP0 of TEX0_1                                                      |
| +0x1E  | 2    | u16    | CBP of TEX0_1                                                       |
| +0x20  | 32   | -      | Zeros                                                               |
| +0x40  | 16   | -      | GIFtag, always `01 80 00 00 00 00 00 70 EE EE FE 0F 00 00 00 00`    |
| +0x50  | 80   | -      | Five GS registers as A+D pairs (below)                              |
| +0xA0  | 32   | f32[8] | The sprite's quad (see [Texture coordinates](#texture-coordinates)) |

### Registers

Each register is an A+D pair: a u64 value, then the u64 GS address of the register.

| Offset | Register | Address |
|--------|----------|---------|
| +0x50  | TEX1_1   | 0x14    |
| +0x60  | TEX2_1   | 0x16    |
| +0x70  | TEX0_1   | 0x06    |
| +0x80  | ALPHA_1  | 0x42    |
| +0x90  | CLAMP_1  | 0x08    |

MGTools reads the named fields of each value; every other bit is 0. The fields, as lowest bit and width in bits:

| Register          | Fields                                                                                                                  |
|-------------------|-------------------------------------------------------------------------------------------------------------------------|
| TEX0_1 and TEX2_1 | TBP0 0:14, TBW 14:6, PSM 20:6, TW 26:4, TH 30:4, TCC 34:1, TFX 35:2, CBP 37:14, CPSM 51:4, CSM 55:1, CSA 56:5, CLD 61:3 |
| TEX1_1            | LCM 0:1, MXL 2:3, MMAG 5:1, MMIN 6:3, MTBA 9:1, L 19:2, K 32:12                                                         |
| ALPHA_1           | A 0:2, B 2:2, C 4:2, D 6:2, FIX 32:8                                                                                    |
| CLAMP_1           | WMS 0:2, WMT 2:2, MINU 4:10, MAXU 14:10, MINV 24:10, MAXV 34:10                                                         |

### Texture coordinates

The coordinates, the quad and the copies of TBP0 and CBP follow from the registers, so the JSON does not hold them.
TEX0_1 gives the page size, 2^TW texels across and 2^TH down, and CLAMP_1 the rectangle on each axis:

- When WMS (across) or WMT (down) is 2, a region clamp, the sprite starts at (MIN + 0.5) / size and reaches
  (MAX - MIN) / size, where MIN and MAX are MINU and MAXU, or MINV and MAXV.
- With any other mode, the sprite covers the whole page on that axis: it starts at 0 and reaches 1.

The quad holds eight float32 values: `-width × 0.4999`, `-height × 0.4999`, 1, 1, the centre `u + width / 2` and
`v + height / 2`, 0 and 0. The factor 0.4999, itself a float32, makes the quad stop just short of the texel edges.

Editable form
-------------

Export writes JSON with these keys:

| Key            | Description                                                                                                                     |
|----------------|---------------------------------------------------------------------------------------------------------------------------------|
| `image_rows`   | The image rows of the header                                                                                                    |
| `palette_rows` | The palette rows of the header                                                                                                  |
| `unknown`      | The word at 0x14 of the header                                                                                                  |
| `sprites`      | Per sprite: `code`, its strcode as 8 hex digits; `flag`; and an object per register, named as in the table above, of its fields |

Import writes the zeroed GS memory the rows give, and computes the offsets, the coordinates and the quads.

Checks and refusals
-------------------

Export refuses a file whose size is not the one its header gives ("Not a sprite atlas"), and one that holds anything
MGTools would write otherwise: GS memory that is not zero, coordinates or a quad that do not follow from the
registers, other register addresses, a set bit outside the named fields, another GIFtag or a second image-rows word
that differs. The message names the offset of the first such byte.

Import refuses a field value that is not an integer that fits the field's width, and a region-clamped rectangle whose
MIN is greater than its MAX or whose MAX lies outside its page. The messages name the JSON file and the sprite, such
as `Sprite 0: CLAMP_1 MAXU takes 10 bits, not 1024`.

Worked example
--------------

An atlas of one invented sprite: the rectangle of texels 16 to 47 across and 0 to 15 down, on a page of 128 × 64
texels (TW 7, TH 6), with a region clamp on both axes. Its HD texture is named by the strcode `00d8b1e1`, and the
header reserves 4 image rows and 1 palette row.

```text
0000  00 00 00 00 04 00 00 00 04 00 00 00 01 00 00 00
0010  01 00 00 00 00 00 00 00 00 01 00 00 00 05 00 00
0020  00 00 04 3E 00 00 00 3C 00 00 78 3E 00 00 70 3E
0030  E1 B1 D8 00 00 00 00 00 00 00 00 00 00 04 00 06
0040  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
0050  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
0060  01 80 00 00 00 00 00 70 EE EE FE 0F 00 00 00 00
0070  60 00 00 00 00 00 00 00 14 00 00 00 00 00 00 00
0080  00 80 30 01 04 C0 00 00 16 00 00 00 00 00 00 00
0090  00 84 30 9D 05 C0 00 00 06 00 00 00 00 00 00 00
00A0  44 00 00 00 00 00 00 00 42 00 00 00 00 00 00 00
00B0  0A C1 0B 00 3C 00 00 00 08 00 00 00 00 00 00 00
00C0  4E F3 F7 BD B7 F3 EF BD 00 00 80 3F 00 00 80 3F
00D0  00 00 80 3E 00 00 00 3E 00 00 00 00 00 00 00 00
*
0600
```

- 0x00: the header. 4 image rows twice, 1 palette row, 1 sprite, the word at 0x14, 0, the image offset 0x100 (the
  entry ends at 0xE0) and the palette offset 0x500. The file ends at 0x500 + 256 = 0x600.
- 0x20: u 16.5 / 128 = 0.12890625, v 0.5 / 64 = 0.0078125, width 31 / 128 = 0.2421875 and height
  15 / 64 = 0.234375.
- 0x30: the strcode, 0, the flag 0, TBP0 0x0400 and CBP 0x0600.
- 0x60: the GIFtag, after 32 zero bytes.
- 0x70: TEX1_1 = 0x60 (MMAG 1, MMIN 1); 0x80: TEX2_1; 0x90: TEX0_1; 0xA0: ALPHA_1 = 0x44 (B 1, D 1); 0xB0: CLAMP_1 =
  0x3C000BC10A (WMS 2, WMT 2, MINU 16, MAXU 47, MINV 0, MAXV 15), each followed by its address.
- 0xC0: the quad: -0.12106954, -0.11716407, 1, 1, the centre 0.25 and 0.125, 0 and 0.
- 0xE0 to the end: zeros.

Export writes this JSON, shown here with each register on one line; the file puts every value on a line of its own:

```json
{
  "image_rows": 4,
  "palette_rows": 1,
  "unknown": 0,
  "sprites": [
    {
      "code": "00d8b1e1",
      "flag": 0,
      "TEX1_1": {"LCM": 0, "MXL": 0, "MMAG": 1, "MMIN": 1, "MTBA": 0, "L": 0, "K": 0},
      "TEX2_1": {"TBP0": 0, "TBW": 2, "PSM": 19, "TW": 0, "TH": 0, "TCC": 1, "TFX": 0, "CBP": 1536,
                 "CPSM": 0, "CSM": 0, "CSA": 0, "CLD": 0},
      "TEX0_1": {"TBP0": 1024, "TBW": 2, "PSM": 19, "TW": 7, "TH": 6, "TCC": 1, "TFX": 0, "CBP": 1536,
                 "CPSM": 0, "CSM": 0, "CSA": 0, "CLD": 0},
      "ALPHA_1": {"A": 0, "B": 1, "C": 0, "D": 1, "FIX": 0},
      "CLAMP_1": {"WMS": 2, "WMT": 2, "MINU": 16, "MAXU": 47, "MINV": 0, "MAXV": 15}
    }
  ]
}
```

Setting `MAXU` to 63 widens the sprite to texel 63: import then writes the width 47 / 128 and moves the centre with
it.
