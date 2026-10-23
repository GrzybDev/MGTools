# Textures

A `.ctxr` file holds one texture of the Master Collection engine: 8-bit BGRA texels at full size and, for most
textures, a chain of mipmaps down to 1 × 1. `mgtools ctxr export` writes the full-size level as a PNG image with a JSON
file of its settings next to it, and `mgtools ctxr import` builds the texture back from them, remaking the mipmaps
(see [Usage](../README.md#textures)).

The engine reads a texture from the `_win` folder beside the path its file lists name, such as
`textures/flatlist/_win/*.ctxr`. A few more textures sit in `_win` folders under `Misc/` and `EngineSupport/Fonts/`,
where `console.ctxr` holds the glyphs of the [console font](cfon.md).

Overall layout
--------------

Every number is big-endian. The file is neither compressed nor encrypted.

| Offset | Size   | Contents                                                               |
|--------|--------|------------------------------------------------------------------------|
| 0x00   | 128    | Header                                                                 |
| 0x80   | varies | The levels, from the full size down, each starting at a multiple of 32 |

Header
------

| Offset       | Size | Type    | Description                                                          |
|--------------|------|---------|----------------------------------------------------------------------|
| 0x00         | 4    | char[4] | Magic `TXTR`                                                         |
| 0x04         | 4    | u32     | Version: 5 or 7 (see [Version differences](#version-differences))    |
| 0x08         | 2    | u16     | Width of level 0 in texels                                           |
| 0x0A         | 2    | u16     | Height of level 0 in texels                                          |
| 0x0C         | 2    | u16     | 1                                                                    |
| 0x0E         | 2    | u16     | 0                                                                    |
| 0x10         | 2    | u16     | Pixel format: 0, 8-bit BGRA, the only one that occurs                |
| 0x12         | 1    | u8      | Alpha flag: 1 when the minimum alpha of level 0 is below 255, else 0 |
| 0x13         | 4    | -       | Zeros                                                                |
| 0x17         | 4    | u8[4]   | Minimum of each channel over level 0, in R, G, B, A order            |
| 0x1B         | 4    | u8[4]   | Maximum of each channel over level 0, in R, G, B, A order            |
| 0x1F         | 4, 7 | -       | Constant bytes that depend on the version                            |
| 0x23 or 0x26 | 1    | u8      | Level count: 1, or the full chain                                    |
| -            | -    | -       | Zeros up to 0x80                                                     |

MGTools requires 1 at 0x0C and 0 at 0x0E; their meaning is not known.

Version differences
-------------------

The two versions differ only in the constant bytes after the colour range, which move the level count:

| Version | Bytes from 0x1F        | Level count at | Used by                                 |
|---------|------------------------|----------------|-----------------------------------------|
| 5       | `00 00 00 00`          | 0x23           | `EngineSupport/Fonts/_win/console.ctxr` |
| 7       | `FF FF 00 00 00 00 00` | 0x26           | Every other texture                     |

Levels
------

Each level starts at a file offset that is a multiple of 32, the first at 0x80:

| Offset | Size    | Type       | Description                                                   |
|--------|---------|------------|---------------------------------------------------------------|
| +0x00  | 4       | u32        | Size of the texels in bytes: 4 × width × height               |
| +0x04  | size    | u8[4] each | Texels row by row from the top left, each in B, G, R, A order |
| -      | 0 to 31 | -          | Zeros up to the next file offset that is a multiple of 32     |

Level n is `max(1, width >> n)` × `max(1, height >> n)` texels. A texture has either level 0 alone or the full chain
down to 1 × 1, whose length is the bit length of the longer side: a 256 × 128 texture has 9 levels (256 × 128, 128 × 64,
..., 2 × 1, 1 × 1). The last level is padded like the others, and nothing follows it.

### Mipmaps

Import remakes the mipmaps from level 0 as the game's converter made them. Each channel of a texel of level n,
alpha included, is the mean of the block of level-0 texels it covers, rounded down. The block is 2^n × 2^n texels,
capped on each side at the size of level 0. The mean comes from level 0 directly: halving
the previous level again would round down at every step and give other values. Import makes mipmaps only for textures
whose sides are powers of two.

### Mipmap overrides

A few texels of the shipped mipmaps differ from the computed mean, where the game's converter rounded otherwise.
Export compares every level with the one it computes and lists each texel that differs in `mipmap_overrides`, with
its level, its position and both colours. Import puts the shipped texel back when the texel it computes at that
position still equals `computed`. When an edit of level 0 changed that texel, the computed value stays, so the
mipmaps follow the edit. Overrides outside the remade chain, such as after a resize, are ignored.

Colour range and alpha flag
---------------------------

The header holds the minimum (0x17) and the maximum (0x1B) of each channel over the texels of level 0, in R, G, B, A
order although the texels are stored as B, G, R, A. The flag at 0x12 is 1 when the minimum alpha is below 255, that
is when any texel of level 0 is not fully opaque. The mipmap levels play no part in either. Import computes all three
from the image, so an edited image updates them.

Many textures use the PS2 alpha scale, where 0x80 is opaque. Their alpha never reaches 255, so their flag is 1. The
tool keeps the alpha as stored and never rescales it.

Editable form
-------------

Export writes an RGBA PNG image of level 0, with the alpha as stored, and a JSON file of the same name next to it:

| Key                | Description                                                                                           |
|--------------------|-------------------------------------------------------------------------------------------------------|
| `version`          | 5 or 7                                                                                                |
| `mipmaps`          | `true` when the texture has the full chain of levels                                                  |
| `mipmap_overrides` | Only when needed: `level` (from 1), `x`, `y`, and the `computed` and `shipped` colours as `#rrggbbaa` |

Import reads the PNG image in any mode and converts it to RGBA, so an image saved without alpha imports as fully
opaque (255). The size of the image becomes the size of the texture: a resized image gets the header and the mipmap
chain of its new size.

Checks and refusals
-------------------

Export refuses a file that:

- does not start with `TXTR`;
- has a version other than 5 or 7, or a pixel format other than 0;
- has a level count that is neither 1 nor the full chain;
- has more than one level on sides that are not powers of two, as import cannot remake their mipmaps;
- has a level whose size is not 4 bytes per texel;
- holds anything MGTools would write otherwise, such as other values in the constant words, a colour range or alpha
  flag that does not match level 0, padding that is not zero or data after the last level. The message names the
  offset of the first such byte.

Import refuses a JSON file whose version is not 5 or 7, `mipmaps` set for an image whose sides are not powers of
two, and an override colour not written as `#rrggbbaa`. The messages name the JSON file.

Worked example
--------------

A 2 × 2 texture of version 7 with mipmaps, of four invented texels:

| Texel  | Colour (RGBA) | Stored (BGRA) |
|--------|---------------|---------------|
| (0, 0) | `#0000ffff`   | `FF 00 00 FF` |
| (1, 0) | `#00ff00ff`   | `00 FF 00 FF` |
| (0, 1) | `#ff000080`   | `00 00 FF 80` |
| (1, 1) | `#ffffff40`   | `FF FF FF 40` |

```text
0000  54 58 54 52 00 00 00 07 00 02 00 02 00 01 00 00
0010  00 00 01 00 00 00 00 00 00 00 40 FF FF FF FF FF
0020  FF 00 00 00 00 00 02 00 00 00 00 00 00 00 00 00
*
0080  00 00 00 10 FF 00 00 FF 00 FF 00 FF 00 00 FF 80
0090  FF FF FF 40 00 00 00 00 00 00 00 00 00 00 00 00
00A0  00 00 00 04 7F 7F 7F AF 00 00 00 00 00 00 00 00
00B0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00C0
```

- 0x04: version 7; 0x08 and 0x0A: 2 × 2 texels; 0x0C: 1; 0x10: pixel format 0.
- 0x12: alpha flag 1, as the minimum alpha is 0x40.
- 0x17: minimum `00 00 00 40` and 0x1B: maximum `FF FF FF FF`, in R, G, B, A order.
- 0x1F: `FF FF` and five zeros, the bytes of version 7, then the level count 2 at 0x26.
- 0x80: level 0, 16 bytes of texels, then zeros up to 0xA0.
- 0xA0: level 1, 4 bytes holding one texel, then zeros up to 0xC0, the end of the file. Its blue is
  (255 + 0 + 0 + 255) / 4 = 127.5, rounded down to 0x7F, and its alpha (255 + 255 + 128 + 64) / 4 = 175.5, rounded
  down to 0xAF.

Export writes `texture.png` and `texture.json`:

```json
{
  "version": 7,
  "mipmaps": true
}
```

Had the file shipped `7F 7F 7F AE` as its 1 × 1 level, export would add the texel to the settings, and import would
write it back as long as level 0 still averages to `#7f7f7faf`:

```json
{
  "version": 7,
  "mipmaps": true,
  "mipmap_overrides": [
    {
      "level": 1,
      "x": 0,
      "y": 0,
      "computed": "#7f7f7faf",
      "shipped": "#7f7f7fae"
    }
  ]
}
```

The same texels in a texture of version 5 without mipmaps differ from 0x1F on: four zeros, then the level count 1
at 0x23, and the file ends at 0xA0, after level 0.
