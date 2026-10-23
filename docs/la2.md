# 2D layouts

A `.la2` file holds a 2D scene of a HUD or menu of the Master Collection: a node tree, the items it draws (such as a
text with the font and sprite it is drawn with), the animations that show those items, the sprites and colours they
use, and the glyph tables of the fonts. `mgtools la2 export` writes a layout as JSON, with its texts in Latin-1 and
its offsets replaced by indices, and `mgtools la2 import` builds it back, checking that the font of each text has a
glyph for each of its characters (see [Usage](../README.md#2d-layouts)).

In English the games read `fr/stage/{mg1,mg2}/cache/*.la2`, `assets/la2/us/*.la2` and
`assets/la2/fr/time_paradox.la2`; the other languages have layouts in their own `stage` and `assets/la2` folders.

Overall layout
--------------

Every number is little-endian, and every offset counts from the start of the file. The file is neither compressed nor
encrypted. A header is followed by nine sections, each starting where the one before ends:

| Part      | Contents                                     |
|-----------|----------------------------------------------|
| Header    | 0x34 bytes, then the strcodes of the atlases |
| Section 0 | The scene header and the node tree           |
| Section 1 | Items                                        |
| Section 2 | Animations                                   |
| Section 3 | Animation names                              |
| Section 4 | Sprites                                      |
| Section 5 | Colours                                      |
| Section 6 | Records whose meaning is not known           |
| Section 7 | Records whose meaning is not known           |
| Section 8 | Fonts                                        |
| Padding   | Zeros up to a multiple of 16 bytes           |

Names are strcodes, the 24-bit hash of an ASCII name that [GCX scripts](gcx.md) use too, stored as u32: for each
byte of the name, the code is rotated left by 5 bits within 24 bits and the byte is added, modulo 2^24, and a name
that hashes to 0 gets 1. Layouts store only the codes, and the JSON writes them as 8 hex digits.

Header
------

| Offset | Size      | Type  | Description                                             |
|--------|-----------|-------|---------------------------------------------------------|
| 0x00   | 2         | u16   | Version: 7                                              |
| 0x02   | 2         | u16   | 1                                                       |
| 0x04   | 4         | u32   | Bits 0 to 27: offset of section 0. Bits 28 to 31: flags |
| 0x08   | 4         | u32   | Offset of section 1                                     |
| 0x0C   | 4         | u32   | Offset of section 2                                     |
| 0x10   | 4         | u32   | Offset of section 3                                     |
| 0x14   | 4         | u32   | 0x30, the offset of the atlas count                     |
| 0x18   | 4         | u32   | 0                                                       |
| 0x1C   | 4         | u32   | Offset of section 4                                     |
| 0x20   | 4         | u32   | Offset of section 5                                     |
| 0x24   | 4         | u32   | Offset of section 6                                     |
| 0x28   | 4         | u32   | Offset of section 7                                     |
| 0x2C   | 4         | u32   | Offset of section 8                                     |
| 0x30   | 4         | u32   | Atlas count                                             |
| 0x34   | 4 × count | u32[] | Strcodes of the atlases                                 |

Section 0 starts right after the atlases, at 0x34 + 4 × atlas count. The meaning of the four flag bits is not known.

Records
-------

Items, tracks and sections 5 to 7 are lists of typed records:

| Offset | Size     | Type | Description                                |
|--------|----------|------|--------------------------------------------|
| +0x00  | 2        | u16  | Type                                       |
| +0x02  | 2        | u16  | Size of the record, these 4 bytes included |
| +0x04  | size - 4 | -    | Payload                                    |

A record of type 0 with no payload ends an item. A record of type 0 or 3 with no payload ends a track.

Section 0: scene
----------------

The section starts with 22 u16 words:

| Word     | Offset | Description                                          |
|----------|--------|------------------------------------------------------|
| 0        | +0x00  | Node count                                           |
| 1        | +0x02  | Sum of the weights of the nodes of kinds 8 and 9     |
| 2        | +0x04  | Number of refs of all nodes                          |
| 3 to 7   | +0x06  | Five words whose meaning is not known                |
| 8        | +0x10  | Number of nodes of kind 10                           |
| 9 to 19  | +0x12  | Number of nodes of each kind, from kind 0 to kind 10 |
| 20 to 21 | +0x28  | 0                                                    |

The nodes follow, parents first: each node's parent is a node before it.

| Offset | Size      | Type         | Description                                                                                    |
|--------|-----------|--------------|------------------------------------------------------------------------------------------------|
| +0x00  | 4         | u32          | Name strcode                                                                                   |
| +0x04  | 2         | u16          | Kind                                                                                           |
| +0x06  | 1         | u8           | A value that follows from the kind (table below)                                               |
| +0x07  | 1         | u8           | A byte whose meaning is not known                                                              |
| +0x08  | 2         | u16          | The node's own index, from 1                                                                   |
| +0x0A  | 2         | u16          | Parent: the index of an earlier node, or 0 for a root                                          |
| +0x0C  | 2         | u16          | Index of the first node after this node's subtree, or 0 when the subtree reaches the last node |
| +0x0E  | 2         | u16          | Weight (table below)                                                                           |
| +0x10  | 4         | u32          | Ref count                                                                                      |
| +0x14  | 4 × count | (u16, u16)[] | Refs, pairs whose meaning is not known                                                         |

| Kind | Byte at +0x06 | Weight                                   |
|------|---------------|------------------------------------------|
| 0    | 1             | 1                                        |
| 1    | 1             | 1                                        |
| 2    | 2             | 1                                        |
| 3    | 6             | 1                                        |
| 6    | 0             | 4                                        |
| 7    | 0             | 2                                        |
| 8    | 0             | 5                                        |
| 9    | 0             | The sum of the second values of its refs |
| 10   | 14            | 1                                        |

MGTools knows no other kinds.

Section 1: items
----------------

A u32 item count, then the items:

| Offset | Size | Type | Description                              |
|--------|------|------|------------------------------------------|
| +0x00  | 2    | u16  | Record count, the end record included    |
| +0x02  | 2    | u16  | Size of the item, these 4 bytes included |
| +0x04  | -    | -    | The records, then the end record         |

MGTools decodes three types of item records and keeps the payload of every other type as it is:

| Type | Payload                                                                                 |
|------|-----------------------------------------------------------------------------------------|
| 7    | Sprite: u32, the index of a sprite of section 4, from 1                                 |
| 13   | Text: u32 length, the text's bytes, then 1 to 4 zero bytes up to a multiple of 4        |
| 24   | Text style: s16 tracking, u16 align, u32 font, the index of a font of section 8, from 1 |

### Texts

A text's bytes are the codes of its glyphs in the font that its item's text style names, except 0x0A, which breaks
the line. The JSON shows each byte as the Latin-1 character of the same number. A text can only use characters that
have a glyph in its font: adding a letter to a text needs a glyph with its code in that font. Import checks this for
every item that has both a text and a text style.

Section 2: animations
---------------------

A u32 animation count, then the animations:

| Offset | Size | Type | Description                                   |
|--------|------|------|-----------------------------------------------|
| +0x00  | 4    | u32  | Track count                                   |
| +0x04  | 4    | u32  | Size of the animation, these 8 bytes included |
| +0x08  | -    | -    | The tracks                                    |

Each track:

| Offset | Size | Type | Description                                    |
|--------|------|------|------------------------------------------------|
| +0x00  | 2    | u16  | Target                                         |
| +0x02  | 2    | u16  | Key count                                      |
| +0x04  | 4    | u32  | Size of the track, these 8 bytes included      |
| +0x08  | -    | -    | The records, then the end record (type 0 or 3) |

The key count is the number of records, the end record included, less one for each delay record (type 4) that is
directly followed by an event record (type 1): such a pair makes a single key.

Two types of track records point at an item, by the offset of the item's first byte. MGTools keeps the payload of
every other type as it is.

| Type | Payload                                         |
|------|-------------------------------------------------|
| 7    | Show: u32 offset of an item                     |
| 8    | Show at a time: u32 time, u32 offset of an item |

Type 7 means a sprite among the records of an item, and showing an item among those of a track.

Sections 3 to 8
---------------

Each of these sections starts with a u32 count.

| Section | Entries                                                                                                |
|---------|--------------------------------------------------------------------------------------------------------|
| 3       | Animation names, 8 bytes each: u32 strcode of the name, u32 offset of the animation's first byte       |
| 4       | Sprites, 8 bytes each: u32 strcode of the sprite, u32 strcode of its atlas                             |
| 5       | Colour records: the type is the number of colours, the payload 4 bytes per colour, in R, G, B, A order |
| 6       | Records whose meaning is not known                                                                     |
| 7       | Records whose meaning is not known                                                                     |
| 8       | Fonts                                                                                                  |

A font:

| Offset | Size       | Type | Description                            |
|--------|------------|------|----------------------------------------|
| +0x00  | 4          | u32  | 0                                      |
| +0x04  | 2          | u16  | Glyph count                            |
| +0x06  | 2          | u16  | Size of the font: 8 + 16 × glyph count |
| +0x08  | 16 × count | -    | The glyphs                             |

A glyph:

| Offset | Size | Type | Description                                               |
|--------|------|------|-----------------------------------------------------------|
| +0x00  | 2    | u16  | Width                                                     |
| +0x02  | 2    | u16  | Height                                                    |
| +0x04  | 2    | u16  | u0: left edge of its box in the font's sprite, 0 to 65535 |
| +0x06  | 2    | u16  | u1: right edge                                            |
| +0x08  | 2    | u16  | v0: top edge                                              |
| +0x0A  | 2    | u16  | v1: bottom edge                                           |
| +0x0C  | 4    | u32  | Code: the byte that texts use for this glyph              |

Editable form
-------------

Export writes JSON with these keys:

| Key                | Description                                                                                              |
|--------------------|----------------------------------------------------------------------------------------------------------|
| `flags`            | Bits 28 to 31 of the word at 0x04                                                                        |
| `atlases`          | The atlas strcodes                                                                                       |
| `scene`            | Words 3 to 7 of the scene header                                                                         |
| `nodes`            | Per node: `name`, `kind`, `parent`, `unknown` (the byte at +0x07) and `refs` when it has any             |
| `items`            | Per item, its records without the end record                                                             |
| `animations`       | Per animation, its tracks: `target`, `end` (the type of the end record) and `records`                    |
| `animation_names`  | `name` and `animation`                                                                                   |
| `sprites`          | `sprite` and `atlas`                                                                                     |
| `colours`          | Per record, its colours as `#rrggbbaa`                                                                   |
| `table6`, `table7` | The records of sections 6 and 7                                                                          |
| `fonts`            | Per font, its glyphs: `char`, the code as a character, then `width`, `height`, `u0`, `u1`, `v0` and `v1` |

Records appear as `{"type": 13, "text": "..."}`, `{"type": 24, "tracking": 0, "align": 1, "font": 1}` and
`{"type": 7, "sprite": 1}` among item records, as `{"type": 7, "item": 0}` and `{"type": 8, "time": 30, "item": 0}`
among track records, and as `{"type": N, "data": "<hex>"}` otherwise, also for a type 7 or 24 item record whose
payload is not 4 or 8 bytes long.

Items and animations, which the file points at by offset, are named by their index from 0. Node parents, the `sprite`
of a type 7 item record and the `font` of a text style keep the file's indices from 1.

Import computes everything else: the counts, sizes and offsets, the derived node fields, the counts of the scene
header, the key counts, the types of the colour records and the constant words. A longer text therefore moves every
section after it, and the show records and animation names point at the new offsets.

Checks and refusals
-------------------

Export refuses a layout that:

- is of another version than 7;
- has an item or track that does not end with its end record;
- has a show record or animation name that points at an offset where no item or animation starts;
- holds anything MGTools would write otherwise. The message names the offset of the first such byte, or the reason
  the layout cannot be written, such as a node of a kind MGTools does not know.

Import refuses:

- a node of a kind other than 0, 1, 2, 3, 6, 7, 8, 9 or 10, and a parent that is not an earlier node;
- a show record or animation name whose item or animation the layout does not have;
- a colour not written as `#rrggbbaa`;
- a text with a character outside Latin-1;
- a text whose item's text style names a font the layout does not have, or whose font has no glyph for one of its
  characters (line breaks need none).

The messages name the JSON file and the item, such as `Item 0: font 1 has no glyph for 'C'`.

Worked example
--------------

A layout of invented data: one atlas, a root node and a child of kind 3, an item that draws the text `GO`, a line
break and `OK` with sprite 1 and font 1, an animation whose one track shows that item, a sprite, a white colour and a
font of three glyphs. The names hash to these strcodes:

| Name        | Strcode    |
|-------------|------------|
| `hud_atlas` | `00b77e57` |
| `root`      | `003aca54` |
| `label`     | `00f21512` |
| `open`      | `00394d0e` |
| `hud_font`  | `00282842` |

The file is 0x150 bytes long:

```text
0000  07 00 01 00 38 00 00 00 8C 00 00 00 BC 00 00 00
0010  DC 00 00 00 30 00 00 00 00 00 00 00 E8 00 00 00
0020  F4 00 00 00 00 01 00 00 04 01 00 00 08 01 00 00
0030  01 00 00 00 57 7E B7 00 02 00 00 00 00 00 02 00
0040  02 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00
0050  01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
0060  00 00 00 00 54 CA 3A 00 00 00 01 00 01 00 00 00
0070  00 00 01 00 00 00 00 00 12 15 F2 00 03 00 06 00
0080  02 00 01 00 00 00 01 00 00 00 00 00 01 00 00 00
0090  04 00 2C 00 07 00 08 00 01 00 00 00 18 00 0C 00
00A0  00 00 01 00 01 00 00 00 0D 00 10 00 05 00 00 00
00B0  47 4F 0A 4F 4B 00 00 00 00 00 04 00 01 00 00 00
00C0  01 00 00 00 1C 00 00 00 02 00 02 00 14 00 00 00
00D0  07 00 08 00 90 00 00 00 00 00 04 00 01 00 00 00
00E0  0E 4D 39 00 C0 00 00 00 01 00 00 00 42 28 28 00
00F0  57 7E B7 00 01 00 00 00 01 00 08 00 FF FF FF FF
0100  00 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00
0110  03 00 38 00 0C 00 10 00 00 00 00 20 00 00 00 40
0120  47 00 00 00 0C 00 10 00 00 20 00 40 00 00 00 40
0130  4B 00 00 00 0C 00 10 00 00 40 00 60 00 00 00 40
0140  4F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

| Offset | Bytes                                                         | Meaning                                                                                                   |
|--------|---------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| 0x00   | `07 00 01 00`                                                 | Version 7, then 1                                                                                         |
| 0x04   | `38 00 00 00`                                                 | Flags 0, section 0 at 0x38                                                                                |
| 0x08   | `8C 00 00 00` ... `08 01 00 00`                               | Sections 1 to 3 at 0x8C, 0xBC and 0xDC; 0x30 and 0; sections 4 to 8 at 0xE8, 0xF4, 0x100, 0x104 and 0x108 |
| 0x30   | `01 00 00 00 57 7E B7 00`                                     | One atlas, `hud_atlas`                                                                                    |
| 0x38   | `02 00 00 00 00 00`                                           | 2 nodes; no weight of kinds 8 and 9; no refs                                                              |
| 0x3E   | `02 00 02 00 01 00 00 00 00 00`                               | The five scene words                                                                                      |
| 0x48   | `00 00`, then 11 words                                        | No node of kind 10; one node of kind 0 (0x4A), one of kind 3 (0x50)                                       |
| 0x60   | `00 00 00 00`                                                 | The two zero words                                                                                        |
| 0x64   | `54 CA 3A 00 00 00 01 00 01 00 00 00 00 00 01 00 00 00 00 00` | Node 1, `root`: kind 0, byte 1, `unknown` 0, index 1, no parent, end 0, weight 1, no refs                 |
| 0x78   | `12 15 F2 00 03 00 06 00 02 00 01 00 00 00 01 00 00 00 00 00` | Node 2, `label`: kind 3, byte 6, index 2, parent 1, end 0, weight 1                                       |
| 0x8C   | `01 00 00 00`                                                 | Section 1: one item                                                                                       |
| 0x90   | `04 00 2C 00`                                                 | The item: 4 records, 44 bytes                                                                             |
| 0x94   | `07 00 08 00 01 00 00 00`                                     | Sprite 1                                                                                                  |
| 0x9C   | `18 00 0C 00 00 00 01 00 01 00 00 00`                         | Text style: tracking 0, align 1, font 1                                                                   |
| 0xA8   | `0D 00 10 00 05 00 00 00 47 4F 0A 4F 4B 00 00 00`             | Text of 5 bytes, `GO`, line break, `OK`, and 3 zero bytes                                                 |
| 0xB8   | `00 00 04 00`                                                 | End of the item                                                                                           |
| 0xBC   | `01 00 00 00`                                                 | Section 2: one animation                                                                                  |
| 0xC0   | `01 00 00 00 1C 00 00 00`                                     | The animation: 1 track, 28 bytes                                                                          |
| 0xC8   | `02 00 02 00 14 00 00 00`                                     | The track: target 2, 2 keys, 20 bytes                                                                     |
| 0xD0   | `07 00 08 00 90 00 00 00`                                     | Show the item at 0x90                                                                                     |
| 0xD8   | `00 00 04 00`                                                 | End of the track                                                                                          |
| 0xDC   | `01 00 00 00 0E 4D 39 00 C0 00 00 00`                         | Section 3: `open` names the animation at 0xC0                                                             |
| 0xE8   | `01 00 00 00 42 28 28 00 57 7E B7 00`                         | Section 4: sprite `hud_font` in atlas `hud_atlas`                                                         |
| 0xF4   | `01 00 00 00 01 00 08 00 FF FF FF FF`                         | Section 5: one record of 1 colour, white                                                                  |
| 0x100  | `00 00 00 00`, `00 00 00 00`                                  | Sections 6 and 7: no records                                                                              |
| 0x108  | `01 00 00 00 00 00 00 00 03 00 38 00`                         | Section 8: one font, 3 glyphs, 56 bytes                                                                   |
| 0x114  | `0C 00 10 00 00 00 00 20 00 00 00 40 47 00 00 00`             | Glyph `G`: 12 × 16, u 0 to 8192, v 0 to 16384                                                             |
| 0x124  |                                                               | Glyphs `K` and `O`                                                                                        |
| 0x144  |                                                               | 12 zero bytes up to 0x150, a multiple of 16                                                               |

Export writes this JSON, shown here with short lists on one line; the file puts every value on a line of its own:

```json
{
  "flags": 0,
  "atlases": ["00b77e57"],
  "scene": [2, 2, 1, 0, 0],
  "nodes": [
    {"name": "003aca54", "kind": 0, "parent": 0, "unknown": 0},
    {"name": "00f21512", "kind": 3, "parent": 1, "unknown": 0}
  ],
  "items": [
    [
      {"type": 7, "sprite": 1},
      {"type": 24, "tracking": 0, "align": 1, "font": 1},
      {"type": 13, "text": "GO\nOK"}
    ]
  ],
  "animations": [
    [
      {"target": 2, "end": 0, "records": [{"type": 7, "item": 0}]}
    ]
  ],
  "animation_names": [{"name": "00394d0e", "animation": 0}],
  "sprites": [{"sprite": "00282842", "atlas": "00b77e57"}],
  "colours": [["#ffffffff"]],
  "table6": [],
  "table7": [],
  "fonts": [
    [
      {"char": "G", "width": 12, "height": 16, "u0": 0, "u1": 8192, "v0": 0, "v1": 16384},
      {"char": "K", "width": 12, "height": 16, "u0": 8192, "u1": 16384, "v0": 0, "v1": 16384},
      {"char": "O", "width": 12, "height": 16, "u0": 16384, "u1": 24576, "v0": 0, "v1": 16384}
    ]
  ]
}
```

Changing the text to `GOOK` imports as it is. Changing it to `GO!` is refused, as font 1 has no glyph for `!`;
adding `{"char": "!", ...}` to the font, with the box of a `!` in the font's sprite, lets it through.
