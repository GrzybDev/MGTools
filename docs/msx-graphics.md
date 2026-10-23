# MSX graphics

The palettes, pictures, screens and sprite frame rectangles of the [MSX resource files](msx-resource.md).
`mgtools resource export` writes them as PNG images and JSON, and `mgtools resource import` builds them back (see
[Usage](../README.md#resource-files)). Positions such as `24.005` name nodes of the resource file as described there.

Sections
--------

| Data             | Metal Gear                                                     | Metal Gear 2: Solid Snake                                          |
|------------------|----------------------------------------------------------------|--------------------------------------------------------------------|
| Palettes         | Section 74, one palette                                        | Section 46                                                         |
| Pictures         | Sections 0-17 from record 2 (tile sets), 41-70 (sprite sheets) | Sections 24 (sprite sheets), 25 (shared tiles), 26-45 (area tiles) |
| Screens          | Section 76                                                     | Section 47                                                         |
| Frame rectangles | Record 0 of each actor, `40.NNN.000`                           | The cell atlas, `00.042`                                           |
| Sprite sets      | -                                                              | `01.006`                                                           |

An empty leaf where a picture would be stays as it is, in `raw/`.

Palettes
--------

A palette is a leaf of 4-byte colours with no header; it holds as many colours as its size divided by 4.

| Offset | Size | Type | Description      |
|--------|------|------|------------------|
| 0      | 1    | u8   | Blue             |
| 1      | 1    | u8   | Green            |
| 2      | 1    | u8   | Red              |
| 3      | 1    | u8   | Unused, always 0 |

MGTools refuses a palette whose size is not a multiple of 4 or whose unused byte is not 0. `palettes.json` lists the
palettes in order, each as a list of `#rrggbb` colours; import refuses a palette of more than 256 colours.

Pictures
--------

A picture is an indexed image: a palette index for each pixel, with no palette, compression or row padding.

| Offset | Size           | Type   | Description                                          |
|--------|----------------|--------|------------------------------------------------------|
| 0      | 4              | u32 LE | Width                                                |
| 4      | 4              | u32 LE | Height                                               |
| 8      | width × height | u8[]   | Palette index of each pixel, row by row from the top |

MGTools refuses a picture whose data is not exactly width × height bytes. The game decides which colours the 256
indices show (see [Colours of the pictures](#colours-of-the-pictures)) and never draws index 0.

Screens
-------

A screen is 512 × 424 pixels in 651,266 bytes, with no header.

| Offset  | Size    | Type    | Description                                                |
|---------|---------|---------|------------------------------------------------------------|
| 0       | 651,264 | u8[3][] | Blue, green and red of each pixel, row by row from the top |
| 651,264 | 2       | bytes   | `00 00`                                                    |

MGTools refuses a screen of another size or with other end bytes. Each game has two.

Colours of the pictures
-----------------------

MGTools rebuilds the colour of each of the 256 indices as the game shows them where it draws a picture. Indices no
palette fills have no colour.

### Metal Gear

Every picture shows the one palette of section 74: index n shows colour n. MGTools refuses a palettes section with
another number of palettes.

### Metal Gear 2: Solid Snake

The game keeps one 256-colour table and loads palettes into parts of it as the screen changes, so the colours of a
picture depend on where it is drawn. A palette fills as many entries as it has colours, from the index it is loaded
at.

Tile sheets show one palette loaded at index 192. Sheet n of section 25 shows palette 33 + n, and sheet n of an area
section shows the first palette of that section + n:

| Section | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 | 34 | 35 | 36 | 37 | 38 | 39 | 40 | 41 | 42 | 43 | 44 | 45 |
|---------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| First   | 0  | 1  | 3  | 5  | 7  | 9  | 11 | 13 | 15 | 16 | 17 | 19 | 21 | 23 | 25 | 26 | 27 | 28 | 29 | 31 |

Sprite sheets show the palettes of the sprite sets that load them. The first case that applies to the sheet holds:

| Sheet                                                    | Palettes, at index          |
|----------------------------------------------------------|-----------------------------|
| Loaded by set 21 (title)                                 | 41 at 0, 37 at 96           |
| Sheet 35, 42, 43 or 66, loaded by set 17 (the last area) | 41 at 0, 36 at 64, 37 at 96 |
| Loaded by set 22 (versus)                                | 41 at 0, 36 at 64, 40 at 96 |
| Any other                                                | 41 at 0, 36 at 64, 39 at 96 |

Only the ending draws sheets 35, 42, 43 and 66, though the set of the last area loads them. MGTools refuses a
palette number the palettes section lacks and a palette too long for the index it is loaded at.

### Sprite sets

Leaf `01.006` holds a record of 82 bytes for each sprite set, numbered from 0. Byte n of a record is non-zero when the
set loads sheet n of section 24; the last byte is an end marker. MGTools reads the leaf only to choose the colours of
the sprite sheets and refuses to export or import sprite sheets without it.

Frame rectangles
----------------

A rectangle table lists where the frames of sprites lie in the sprite sheets, in 6-byte records with no header:

| Offset | Size | Type | Description                               |
|--------|------|------|-------------------------------------------|
| 0      | 1    | u8   | Sheet (Metal Gear) or slot (Metal Gear 2) |
| 1      | 1    | u8   | Number of the record, from 0              |
| 2      | 1    | u8   | x, the left edge in the sheet             |
| 3      | 1    | u8   | y, the top edge in the sheet              |
| 4      | 1    | u8   | w, the width                              |
| 5      | 1    | u8   | h, the height                             |

A leaf is a rectangle table when its size is a multiple of 6, each record holds its own number and every sheet or
slot is in range. JSON gives each record as an object of `sheet` or `slot`, `x`, `y`, `w` and `h`; the record numbers
follow from the order. Import refuses other keys and values outside their range: 0 to 255 for `x`, `y`, `w` and `h`.

### Metal Gear actors

Section 40 holds a container per actor, and record 0 of most actors is a rectangle table. Its first byte is the sprite
sheet minus 41, so `sheet` runs from 41 to 70 in `actors.json`, which maps each actor number to its rectangles. A
record 0 that is empty or no rectangle table stays in `raw/`.

### Metal Gear 2 cell atlas

Leaf `00.042` holds a sequence of nodes in the format of the [resource file](msx-resource.md#nodes). Each node is a
leaf, a group of cells, holding a rectangle table. A cell's `slot` runs from 0 to 83 and is its sheet in section 24
plus 3; slots 0 to 2 are not sprite sheets. `cells.json` lists the groups in order. Export refuses a file without the
cell atlas or with a group that is a container or no rectangle table.

Editable form
-------------

A picture becomes an indexed PNG image whose palette shows the colours of
[where the game draws it](#colours-of-the-pictures). Index 0 is transparent. Each index without a colour gets a filler
colour no other index shows: red 255, blue 255 minus the index, and the first green that keeps it unique.

Import takes the indices of an indexed PNG as they are when every index it draws still shows the colour export gave
it. Otherwise, as for RGB and RGBA copies that editors save, it maps each pixel back by its colour: alpha 0 gives
index 0, and an opaque colour gives the first index that shows it. It refuses partly transparent pixels and colours no
index shows.

When a palette shows one colour at several indices, a picture may draw it with a later one. `colour_choices` in
`resource.json` then names, for that picture, the index the picture draws most often for the colour, and RGB copies
map the colour to it. An RGB copy keeps every index only when the picture draws each colour with one index.

Screens become RGB PNG images; import refuses one that is not 512 × 424 pixels.

Worked example
--------------

An invented palette of four colours, the last two the same:

```text
0000  00 00 00 00 FF FF FF 00 32 64 C8 00 32 64 C8 00
```

| Index | Bytes         | Colour    |
|-------|---------------|-----------|
| 0     | `00 00 00 00` | `#000000` |
| 1     | `FF FF FF 00` | `#ffffff` |
| 2     | `32 64 C8 00` | `#c86432` |
| 3     | `32 64 C8 00` | `#c86432` |

A Metal Gear picture of 3 × 2 pixels that shows it:

```text
0000  03 00 00 00 02 00 00 00 00 01 02 03 03 01
```

Width 3, height 2, then the rows `00 01 02` and `03 03 01`. In the PNG image, the first pixel is transparent and
indices 4 to 255 get filler colours, starting with `#ff00fb`, `#ff00fa` and `#ff00f9`. The picture draws `#c86432`
twice with index 3 and once with index 2, so `resource.json` holds `"colour_choices": {"SS.NNN": {"#c86432": 3}}` for
it. An RGB copy of the image reads back as `00 01 03` and `03 03 01`: the pixel of index 2 becomes index 3.

A Metal Gear actor whose two frames lie in sheets 41 and 43:

```text
0000  00 00 00 00 10 20 02 01 10 00 10 20
```

```json
[
  {"sheet": 41, "x": 0, "y": 0, "w": 16, "h": 32},
  {"sheet": 43, "x": 16, "y": 0, "w": 16, "h": 32}
]
```

A Metal Gear 2 cell atlas of two groups, the first with one cell of sheet 0 (slot 3), the second empty:

```text
0000  00 00 00 06 03 00 08 08 18 10 00 00 00 00
```

```json
[
  [{"slot": 3, "x": 8, "y": 8, "w": 24, "h": 16}],
  []
]
```
