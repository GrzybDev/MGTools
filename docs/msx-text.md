# MSX texts

The texts of the [MSX resource files](msx-resource.md): section 72 in Metal Gear and section 2 in Metal Gear 2: Solid
Snake. `mgtools resource export` writes their strings to a translation document, and `mgtools resource import`
encodes them back after checking each against the font and the limits of the engine (see
[Usage](../README.md#resource-files) and [Translating the games](../README.md#translating-the-games)).

Blocks
------

The text section is a container of leaves, the blocks: 17 in Metal Gear, 24 in Metal Gear 2. MGTools refuses another
number. The kind of a block is fixed by its index.

### Metal Gear

| Block | Kind        | Contents                                                                |
|-------|-------------|-------------------------------------------------------------------------|
| 0-2   | Table       | No text                                                                 |
| 3     | Strings     | Prisoners, hostages and other people                                    |
| 4     | Strings     | Guards, item pick-ups, broadcasts, bosses, events and Big Boss's speech |
| 5     | Strings     | Radio: Big Boss, first set                                              |
| 6     | Strings     | Radio: Big Boss, second set                                             |
| 7     | Strings     | Radio: Schneider                                                        |
| 8     | Strings     | Radio: Diane and Steve                                                  |
| 9     | Strings     | Radio: Jennifer                                                         |
| 10-11 | Table       | No text                                                                 |
| 12    | Warp points | Debug warp points                                                       |
| 13    | Strings     | Radio: opening briefing                                                 |
| 14    | Strings     | Ending: Snake's report, news flash, staff credits and Big Boss          |
| 15    | Strings     | Menus, item and weapon descriptions, boss names and records             |
| 16    | Table       | No text                                                                 |

### Metal Gear 2: Solid Snake

Every block is a list of strings.

| Block | Contents                                 | Block | Contents                                       |
|-------|------------------------------------------|-------|------------------------------------------------|
| 0     | Equipment names and descriptions         | 12    | Big Boss's final talk                          |
| 1     | Weapon names and descriptions            | 13    | Gustava                                        |
| 2     | Codec: Snake calling                     | 14    | Guards and Snake during play                   |
| 3     | Codec: Campbell                          | 15    | Children                                       |
| 4     | Codec: your number one fan and the pilot | 16    | Item pick-ups                                  |
| 5     | Codec: Holly                             | 17    | Opening story                                  |
| 6     | Codec: Kasler                            | 18    | Staff credits                                  |
| 7     | Codec: Dr. Madnar                        | 19    | Bosses and cut-scenes                          |
| 8     | Marv, who speaks Czech, and Gustava      | 20    | Escape and ending cut-scenes                   |
| 9     | Codec: Master Miller                     | 21    | Debug warp-point names, never shown to players |
| 10    | Codec: Jacobsen                          | 22    | Codec contacts, pause and title menus, options |
| 11    | Gray Fox                                 | 23    | Rank code names, boss names and results        |

String records
--------------

A list of strings is a sequence of records with no count, terminator or padding: it ends where the block ends, and
an empty block holds no strings. The engine finds a string by its position, so a translation keeps the number and the
order of the strings.

Metal Gear:

| Offset | Size | Type   | Description                   |
|--------|------|--------|-------------------------------|
| 0      | 1    | u8     | Style                         |
| 1      | 2    | u16 BE | Length n of the text in bytes |
| 3      | n    | bytes  | Text                          |

Metal Gear 2:

| Offset | Size | Type   | Description                   |
|--------|------|--------|-------------------------------|
| 0      | 2    | u16 BE | Length n of the text in bytes |
| 2      | n    | bytes  | Text                          |

A text takes at most 65,535 bytes. The style byte of Metal Gear marks the kind of string:

| Style | Meaning                    |
|-------|----------------------------|
| 0     | Dialogue, message or menu  |
| 1     | Short exclamation          |
| 2     | Item pick-up               |
| 3     | Enemy broadcast            |
| 4     | Radio message              |
| 5     | Boss introduction or alarm |
| 23    | Notice                     |
| 26    | Event message              |

MGTools keeps any other value as it is.

Warp points
-----------

Block 12 of Metal Gear lists debug warp points, one record after another:

| Offset | Size | Type   | Description                                  |
|--------|------|--------|----------------------------------------------|
| 0      | 4    | bytes  | Parameters                                   |
| 4      | 2    | u16 BE | Length n of the name in bytes                |
| 6      | n    | bytes  | Name, in the [character set](#character-set) |
| 6 + n  | 2    | u16 BE | x                                            |
| 8 + n  | 2    | u16 BE | y                                            |
| 10 + n | 1    | u8     | Flag                                         |

MGTools does not interpret the parameters, coordinates or flag; it keeps them in `text.json`.

Character set
-------------

A character takes one or two bytes, and an engine code two or four. MGTools reads a text from the start, taking at
each byte the first rule that applies:

| Bytes                                                                        | Game         | Reads as                                         |
|------------------------------------------------------------------------------|--------------|--------------------------------------------------|
| A lead byte `81`-`9F` or `E0`-`FC`, then a trail byte `40`-`7E` or `80`-`FC` | Both         | A double-byte character (see below)              |
| `5C` and an engine code                                                      | Metal Gear 2 | A placeholder, see [Engine codes](#engine-codes) |
| `7C` and a digit                                                             | Both         | `{btn:N}`, the icon of controller button N       |
| `0A`                                                                         | Both         | A line break                                     |
| `20`-`7E`, except `7B` and `7D`                                              | Both         | ASCII; `5C` is a backslash in Metal Gear         |
| `7F` or `A0`-`DF`, if the charmap names it                                   | Both         | The character of the charmap                     |
| Any other byte                                                               | Both         | `{x:HH}`                                         |

A double-byte character reads as its Shift-JIS (code page 932) character when that character encodes back to the same
two bytes and the charmap gives it no code of its own; otherwise it reads as `{sjis:HHHH}`. In Metal Gear 2, a `5C`
that starts no engine code reads as `{x:5C}`. With `{x:HH}` and `{sjis:HHHH}`, any bytes read back the same.

### Charmaps

Every engine routine reads only `7F` and `A0` to `DF` as one character; every other byte from `80` up is a lead byte to
some routine. The game files store no names for the characters the font draws at these codes, so MGTools reads them
with a charmap: the European one by default, or the Japanese one for a [Japanese font](msx-font.md#version-differences).
`mgtools resource export --charmap` takes the charmap of the `font.json` of an earlier export instead.

European charmap:

|    | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | A | B | C | D | E | F |
|----|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_ |   |   |   |   |   |   |   | č | ě | ů | ř | ý | ž | „ |   |   |
| B_ | à | á | â | ä | À | Á | Â | Ä | è | é | ê | ë | È | É | Ê | Ë |
| C_ | ì | í | î | ï | Ì | Í | Î | Ï | ò | ó | ô | ö | Ò | Ó | Ô | Ö |
| D_ | ù | ú | û | ü | Ù | Ú | Û | Ü | ñ | ç | ß | Ç | ¡ | ¿ | ® | ° |

Japanese charmap, for the lines Marv speaks in Czech:

| Code      | B1 | B2 | B3 | B4 | B5 | B6 | B7 | B8 | B9 |
|-----------|----|----|----|----|----|----|----|----|----|
| Character | á  | č  | ě  | í  | ú  | ů  | ř  | ý  | ž  |

A charmap gives codes `7F` and `A0` to `DF` only, one character each, every character from U+00A0 up and none twice;
MGTools refuses any other.

### Engine codes

Metal Gear 2 starts its engine codes with a backslash, `5C`:

| Bytes                        | Placeholder  | Meaning                                                           |
|------------------------------|--------------|-------------------------------------------------------------------|
| `5C 77` (`\w`)               | `{wait}`     | Waits for a button, then clears the window                        |
| `5C 57` (`\W`)               | `{autowait}` | Waits about half a second, then clears the window                 |
| `5C 72` (`\r`)               | `{r}`        | Marks the partner as the speaker                                  |
| `5C 73` (`\s`)               | `{s}`        | Marks Snake as the speaker                                        |
| `5C 65` (`\e`)               | `{e}`        | Sets an engine flag                                               |
| `5C 66` (`\f`)               | `{f}`        | Draws a picture                                                   |
| `5C 31`-`5C 39`              | `{speed:N}`  | Sets the typing speed: 1, 4, 7 fast, 2, 5, 8 normal, 3, 6, 9 slow |
| `5C 42` and 2 bytes (`\Bxx`) | `{bgm:xx}`   | Changes the music to track xx                                     |
| `5C 53` and 2 bytes (`\Sxx`) | `{se:xx}`    | Plays the sound effect xx                                         |

The two bytes of `{bgm:xx}` and `{se:xx}` are characters from space to `z`, `|` or `~`. Metal Gear refuses these
placeholders and reads `5C` as a backslash. Both games take `{btn:N}`, `{x:HH}` and `{sjis:HHHH}`.

Encoding
--------

Import writes a text back with these rules and refuses anything else, naming the string and the reason:

- A `{` opens a placeholder of the game, and a `}` closes one.
- In Metal Gear 2, a backslash is refused: engine codes are written as placeholders.
- A line break and the ASCII characters from space to `~` take their own byte, so `|` followed by a digit always reads
  back as `{btn:N}`.
- A character of the charmap takes its code; any other character takes its two Shift-JIS bytes. A character with
  neither, including the half-width katakana of single Shift-JIS bytes, needs a code in the charmap.
- `{x:HH}` writes any byte and `{sjis:HHHH}` any two bytes.

Limits
------

Import also refuses texts the game cannot show as they are:

| Check                                                                                                               | Applies to                                                |
|---------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| A single byte from `20` up needs a glyph on font page 0                                                             | Both games                                                |
| A double-byte character needs a glyph on font page 4                                                                | Both games                                                |
| Only space, digits, capitals and `B0` to `DF`, drawn with the 8 × 8 HUD font whose cells are in `images/62.000.png` | European Metal Gear, block 15, strings 3-8, 13-15 and 141 |
| No word longer than a line: 48 bytes in Metal Gear, 45 in Metal Gear 2                                              | European releases, which wrap at spaces                   |
| No line longer than 48 bytes in Metal Gear, 47 in Metal Gear 2                                                      | Japanese releases, which do not wrap                      |
| At most 10 lines a page; `{wait}` and `{autowait}` start a page                                                     | Metal Gear 2, except blocks 17 and 18                     |
| A line break or space after `{wait}`, whose next byte the game hides                                                | Japanese Metal Gear 2                                     |
| No `5C` that starts no engine code, which hangs the game                                                            | Metal Gear 2                                              |

Two of the 47 bytes of a Metal Gear 2 line go to the indent of European lines. Lengths count bytes, placeholders
included; `{wait}` and `{autowait}` count none and start both counts again, of bytes and of lines. The opening story
and the staff credits of Metal Gear 2 (blocks 17 and 18) have pages of more than ten lines, which a routine other than
the message window lays out. In Metal Gear, a blank line starts a page.

Editable form
-------------

Each string is a unit of `text.xlf` (or `text.xliff` or `text.po`) named after its game, block and number, such as
`mg1.b03.e000`. Its notes give the contents of the block, the style, the number of bytes of the original, the line
and page limits and what each placeholder in it does. A string of Metal Gear's block 15 or Metal Gear 2's blocks 21 to
23 whose widest line fits the 512 pixels of the screen is a label the game does not wrap, and its note gives that
width: the page 0 width of each single byte, and 24 pixels for each double-byte character and button icon. Japanese
documents give `ja` as their source language.

`text.json` holds what the units do not:

| Game         | Key       | Description                                                           |
|--------------|-----------|-----------------------------------------------------------------------|
| Metal Gear   | `styles`  | The style of each string, by block (`b03` to `b15`)                   |
| Metal Gear   | `warps`   | Each warp point: `params` in hex, `name` as text, `x`, `y` and `flag` |
| Metal Gear 2 | `strings` | The number of strings of each block (`b00` to `b23`)                  |

The blocks that hold no text go to `text/bNN.bin` as they are. Import refuses a `text.json` without exactly the blocks
of the game, a style that is not a byte, and warp parameters that are not 4 bytes.

Worked example
--------------

An invented Metal Gear block of two strings, read with the European charmap:

```text
0000  00 00 0F 47 61 74 65 20 37 20 69 73 20 6F 70 65
0010  6E 2E 04 00 12 43 61 66 B9 20 61 74 20 7C 32 2E
0020  0A 0A 4F 76 65 72 2E
```

| Offset | Bytes         | Meaning                                                                                 |
|--------|---------------|-----------------------------------------------------------------------------------------|
| 0x00   | `00`          | Style 0                                                                                 |
| 0x01   | `00 0F`       | 15 bytes                                                                                |
| 0x03   | `47` ... `2E` | `Gate 7 is open.`                                                                       |
| 0x12   | `04`          | Style 4                                                                                 |
| 0x13   | `00 12`       | 18 bytes                                                                                |
| 0x15   | `43` ... `2E` | `Café at {btn:2}.`, a blank line, `Over.`; `B9` is `é` and `7C 32` the icon of button 2 |

`text.json` keeps `"b03": [0, 4]` if this were block 3.

An invented Metal Gear 2 string of 30 bytes:

```text
0000  00 1E 4F 70 65 72 61 74 6F 72 5C 72 3A 20 0A 5C
0010  33 53 74 61 6E 64 20 62 79 2E 5C 42 30 37 5C 77
```

It reads as `Operator{r}: `, a line break, then `{speed:3}Stand by.{bgm:07}{wait}`.

An invented warp point named `Test point` at x 300, y 200:

```text
0000  00 01 02 03 00 0A 54 65 73 74 20 70 6F 69 6E 74
0010  01 2C 00 C8 00
```

```json
{"params": "00010203", "name": "Test point", "x": 300, "y": 200, "flag": 0}
```

How some bytes read in each game:

| Bytes   | Metal Gear                     | Metal Gear 2                   |
|---------|--------------------------------|--------------------------------|
| `5C 77` | `\w`                           | `{wait}`                       |
| `5C 41` | `\A`                           | `{x:5C}A`                      |
| `7B 7D` | `{x:7B}{x:7D}`                 | `{x:7B}{x:7D}`                 |
| `82 A0` | `あ`                            | `あ`                            |
| `B9`    | `é` (European), `ž` (Japanese) | `é` (European), `ž` (Japanese) |
