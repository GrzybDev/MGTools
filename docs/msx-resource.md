# MSX resource files

The resource file of Metal Gear or Metal Gear 2: Solid Snake holds the texts, the font, the pictures, the palettes
and the game data of one language in a tree of nodes. `mgtools resource info` lists its sections,
`mgtools resource export` writes it to a folder and `mgtools resource import` builds it back (see
[Usage](../README.md#resource-files)).

Files
-----

| Release                   | Game                      | File                                                                                                  |
|---------------------------|---------------------------|-------------------------------------------------------------------------------------------------------|
| Metal Gear (GOG)          | Metal Gear                | `Resource\<language>.bin`, such as `Resource\English.bin`                                             |
| Master Collection (Steam) | Metal Gear                | `<folder>/stage/mg1/cache/**/<language>.raw`, such as `fr/stage/mg1/cache/ovr_stm/ovr_eu/english.raw` |
| Master Collection (Steam) | Metal Gear 2: Solid Snake | `<folder>/stage/mg2/cache/**/<language>.raw`, such as `fr/stage/mg2/cache/ovr_stm/ovr_eu/english.raw` |

Every release uses the same format, and MGTools reads all of them the same way. It tells the Japanese files apart by
their font (see [MSX fonts](msx-font.md)), which also decides their character set (see [MSX texts](msx-text.md)).

Nodes
-----

The file is a tree of nodes. A node is a 4-byte header followed by its payload, with no padding or alignment between
nodes.

| Offset | Size | Type   | Description                                                    |
|--------|------|--------|----------------------------------------------------------------|
| 0      | 4    | u32 BE | Flags in bits 30-31, size of the payload in bytes in bits 0-29 |
| 4      | size | bytes  | Payload                                                        |

| Flags | Node      | Payload                                               |
|-------|-----------|-------------------------------------------------------|
| 0     | Leaf      | Data, decoded by the position of the leaf (see below) |
| 1     | Container | A sequence of nodes that fills the payload exactly    |
| 2, 3  | -         | Refused                                               |

The engine takes any non-zero flags for a container. The games only use 1, and MGTools refuses 2 and 3 so that every
file it builds back has the same bytes. A payload holds at most 0x3FFFFFFF bytes. MGTools refuses a node that runs
past the end of its parent.

Tree
----

The file is exactly one container, the root. Each child of the root is a section, and every section is a container.
Sections hold leaves and further containers, and a container may be empty. The meaning of a section is fixed by its
index alone.

A node is named by its position: the indices leading from the root to it, section first. Names give the section in two
digits and each further index in three, separated by dots, so `72.003` is leaf 3 of section 72 and `20.000.001` is
leaf 1 of container 0 of section 20. The exported folder names its files this way.

MGTools tells the game by the number of sections: 77 for Metal Gear, 49 for Metal Gear 2. It refuses a file whose
root is not a container of containers or has another number of sections.

### Metal Gear

| Sections | Holds                                                                                                     | Format                                                   |
|----------|-----------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| 0-17     | Tile sets: records 0 and 1 are the tile flags of sets A and B, then the images of A, A dark, B and B dark | Pictures from record 2 ([MSX graphics](msx-graphics.md)) |
| 18-19    | Unused                                                                                                    | Not decoded                                              |
| 20-37    | Rooms                                                                                                     | Not decoded                                              |
| 38-39    | Unused                                                                                                    | Not decoded                                              |
| 40       | Actors, one container each; record 0 of most actors lists the rectangles of their frames                  | [Frame rectangles](msx-graphics.md#frame-rectangles)     |
| 41-70    | Sprite sheets: pictures, then an empty record                                                             | [Pictures](msx-graphics.md#pictures)                     |
| 71       | Script                                                                                                    | Not decoded                                              |
| 72       | Text, 17 blocks                                                                                           | [MSX texts](msx-text.md)                                 |
| 73       | A table per area                                                                                          | Not decoded                                              |
| 74       | The palette of every picture                                                                              | [Palettes](msx-graphics.md#palettes)                     |
| 75       | Font, 5 pages                                                                                             | [MSX fonts](msx-font.md)                                 |
| 76       | Two screens                                                                                               | [Screens](msx-graphics.md#screens)                       |

### Metal Gear 2: Solid Snake

| Sections | Holds                                                          | Format                                                                                                        |
|----------|----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| 0        | Sprite animations; leaf `00.042` is the cell atlas             | Cell atlas: [Frame rectangles](msx-graphics.md#frame-rectangles); the rest not decoded                        |
| 1        | Game tables; leaf `01.006` lists the sheets of each sprite set | Not decoded; export reads the [sprite sets](msx-graphics.md#sprite-sets) for the colours of the sprite sheets |
| 2        | Text, 24 blocks                                                | [MSX texts](msx-text.md)                                                                                      |
| 3        | Scripts                                                        | Not decoded                                                                                                   |
| 4-23     | Area data, one section per area                                | Not decoded                                                                                                   |
| 24       | Sprite sheets                                                  | [Pictures](msx-graphics.md#pictures)                                                                          |
| 25       | Tile sheets shared by every area                               | [Pictures](msx-graphics.md#pictures)                                                                          |
| 26-45    | The tile sheets of each area                                   | [Pictures](msx-graphics.md#pictures)                                                                          |
| 46       | Palettes                                                       | [Palettes](msx-graphics.md#palettes)                                                                          |
| 47       | Two screens                                                    | [Screens](msx-graphics.md#screens)                                                                            |
| 48       | Font, 5 pages                                                  | [MSX fonts](msx-font.md)                                                                                      |

`mgtools resource info` prints this list for a file, with the number of leaves of each section and its size in bytes,
header included.

Editable form
-------------

Export writes each leaf of the tree to exactly one file:

| Leaves                                      | Files                                                                                   |
|---------------------------------------------|-----------------------------------------------------------------------------------------|
| The text section                            | `text.xlf` (`text.xliff`, `text.po`), `text.json` and `text/bNN.bin`                    |
| The font section                            | `font.json` and `font/page0.png` to `font/page4.png`, or `font/page0/` to `font/page4/` |
| The palettes section                        | `palettes.json`                                                                         |
| The screens section and every other picture | `images/SS.NNN.png`                                                                     |
| The frame rectangles                        | `actors.json` (Metal Gear) or `cells.json` (Metal Gear 2)                               |
| Every other leaf, empty pictures included   | `raw/SS.NNN.bin`, the payload as it is                                                  |

`resource.json` names the game (`mg1` or `mg2`), lists the empty containers by position in `empty_containers`, and
keeps the `colour_choices` of the pictures (see [MSX graphics](msx-graphics.md#editable-form)). Export refuses a folder
that is not empty, since import takes every file it finds.

Import rebuilds the tree from the positions of the files and refuses:

- two files for one position, or a position in a section past the last one;
- a gap in the numbering of a container's children, such as `05.002` without `05.001`;
- a position held both by a file and by files of nodes inside it, or both by a file and by `empty_containers`;
- a number of sections other than the game's;
- a PNG image at a position that holds no picture.

Worked example
--------------

The tree below is invented and much smaller than a resource file, which has 77 or 49 sections:

```text
root
├── section 0
│   ├── 00.000      leaf 01 02 03
│   └── 00.001      empty container
└── section 1
    └── 01.000      container
        └── 01.000.000  leaf "AB"
```

It takes 33 bytes:

```text
0000  40 00 00 1D 40 00 00 0B 00 00 00 03 01 02 03 40
0010  00 00 00 40 00 00 0A 40 00 00 06 00 00 00 02 41
0020  42
```

| Offset | Bytes         | Meaning                        |
|--------|---------------|--------------------------------|
| 0x00   | `40 00 00 1D` | Root: container, 29 bytes      |
| 0x04   | `40 00 00 0B` | Section 0: container, 11 bytes |
| 0x08   | `00 00 00 03` | `00.000`: leaf, 3 bytes        |
| 0x0C   | `01 02 03`    | Payload of `00.000`            |
| 0x0F   | `40 00 00 00` | `00.001`: container, empty     |
| 0x13   | `40 00 00 0A` | Section 1: container, 10 bytes |
| 0x17   | `40 00 00 06` | `01.000`: container, 6 bytes   |
| 0x1B   | `00 00 00 02` | `01.000.000`: leaf, 2 bytes    |
| 0x1F   | `41 42`       | Payload of `01.000.000`        |

In a resource folder, the two leaves would be `raw/00.000.bin` and `raw/01.000.000.bin`, and `resource.json` would
list `00.001` in `empty_containers`.
