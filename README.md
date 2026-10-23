# MGTools

A command-line toolkit that converts the files of the PC releases of Metal Gear and Metal Gear 2: Solid Snake, on GOG
and in the Steam Master Collection, to editable forms and back, for translations and mods.

Every conversion is lossless: a file exported and imported back unchanged gives the very same bytes, which the tests
check on every file of both releases. Texts go to translation tools as XLIFF 2.0, XLIFF 1.2 or Gettext PO, pictures and
glyphs become PNG images, structures JSON, and data the tools do not decode stays in `.bin` files.

Table of Contents
-----------------
- [Supported games](#supported-games)
- [Legal notes](#legal-notes)
- [Features](#features)
- [Requirements](#requirements)
- [Installing](#installing)
- [Usage](#usage)
- [File formats](#file-formats)
- [Development](#development)
- [Credits](#credits)

Supported games
---------------

| Release                                                                          | Games                                 |
|----------------------------------------------------------------------------------|---------------------------------------|
| Metal Gear (GOG)                                                                 | Metal Gear                            |
| METAL GEAR & METAL GEAR 2: Solid Snake (Steam, part of Master Collection Vol. 1) | Metal Gear, Metal Gear 2: Solid Snake |

Both releases run the MSX2 games from resource files, one per language, that hold their texts, fonts, pictures and
game data. The Master Collection runs them inside the engine of Bluepoint's Metal Gear Solid HD Collection, whose own
files hold the scripts, layouts, textures and texts around the games. The tools read and write these formats:

| Files                                                                           | Format versions                                                                                                                         |
|---------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| Resource files                                                                  | One format in both releases and every language: 77 sections in Metal Gear, 49 in Metal Gear 2; the Japanese files have sized font pages |
| GCX scripts                                                                     | Plain and Bluepoint (`LCGB`); the game reads the Bluepoint copies                                                                       |
| Textures                                                                        | Versions 5 (`console.ctxr`) and 7                                                                                                       |
| 2D layouts                                                                      | Version 7                                                                                                                               |
| Sprite atlases, console font, TNOF fonts, keepfonts, string tables, sound banks | One format each                                                                                                                         |

### Files the games read

**GOG**: `MetalGear.exe` reads `Resource\<language>.bin`, where `<language>` is the `language` of the `[metalgear]`
section of `settings.ini` (`english` by default), and falls back to `Resource\English.bin`. A translation can therefore
ship as a file of its own, such as `Resource\Polish.bin` with `language=polish`. `settings.exe` only lists the five
shipped languages, so saving its dialog sets English again.

**Steam**: the launcher starts `METAL GEAR.exe` with the language chosen for the game and the region `eu` (`jp` for
Japanese). The engine takes the file lists of each stage and slot page (`manifest.txt` and `bp_assets.txt`) from the
data folder of the language, `fr` for English and French, `gr`, `it`, `sp` or `jp`, and loads each line of the 60 Hz
video mode. It reads a script
from the `_bp` folder beside its path when there is one there, a texture from the `_win` folder beside it, and each
file from the first override folder that holds it (such as `ovr_stm/` and the region's `ovr_eu/`), down to the listed
path. In English, the games read:

| Data                   | Files                                                                                          |
|------------------------|------------------------------------------------------------------------------------------------|
| Metal Gear resources   | `fr/stage/mg1/cache/ovr_stm/ovr_eu/english.raw`                                                |
| Metal Gear 2 resources | `fr/stage/mg2/cache/ovr_stm/ovr_eu/english.raw`                                                |
| Scripts                | `fr/stage/{mg1,mg2}/cache/_bp/00180720.gcx`, `assets/gcx/fr/_bp/*.gcx`                         |
| Layouts                | `fr/stage/{mg1,mg2}/cache/*.la2`, `assets/la2/us/*.la2`, `assets/la2/fr/time_paradox.la2`      |
| Sprite atlases         | `assets/tri/us/*.tri`                                                                          |
| Keepfont               | `assets/raw/us/keepfont_stage_r_sna01_r.raw`                                                   |
| Textures               | `textures/flatlist/_win/*.ctxr` and their overrides, such as `textures/flatlist/ovr_stm/_win/` |
| String tables          | `EngineSupport/stovc.bin` (controllers), `EngineSupport/stovk.bin` (keyboard)                  |
| Sound banks            | `us/stage/{mg1,mg2,r_sna01}/pk0*.sdx` (`jp/stage/...` in Japanese)                             |

The other copies, such as `cache/english.raw` and `cache/00180720.gcx`, are never read, and `cache/ovr_stm/english.raw`
only in the region `us`, which the launcher never passes. French, German and Italian are read from
`<folder>/stage/{mg1,mg2}/cache/ovr_stm/<language>.raw`, Spanish from
`sp/stage/{mg1,mg2}/cache/ovr_stm/ovr_eu/spanish.raw` and Japanese from `jp/stage/{mg1,mg2}/cache/ovr_stm/japanese.raw`.
A translation therefore replaces the copy the game reads, which [`mgtools files`](#game-files) names for any language,
region and controller.

Legal notes
-----------

This repository and its releases contain no files of the games. You need your own copy of a game:

- Metal Gear: [GOG](https://www.gog.com/en/game/metal_gear)
- METAL GEAR & METAL GEAR 2: Solid Snake, also part of the Master Collection Vol. 1:
  [Steam](https://store.steampowered.com/app/2131680/)

The tools only read and write the games' data files. They neither make piracy easier nor bypass or remove any DRM.

Metal Gear and Metal Gear 2: Solid Snake are trademarks of Konami Digital Entertainment. MGTools is not affiliated with
or endorsed by Konami.

Features
--------

- **Resource files (`resource`)**
  - Show which game a resource file belongs to and what each section holds, with its number of leaves and its size
  - Export the texts to one translation document, a unit per string with notes on where the game shows it, how many
    bytes the original takes and which limits apply
  - Export the font as a PNG image per page or per glyph and `font.json`, and import glyphs added for letters the game
    lacks
  - Export the pictures as indexed PNG images with the colours the game shows, and import them back also from RGB and
    RGBA copies
  - Export the palettes, Metal Gear's sprite frame rectangles and Metal Gear 2's cell atlas as JSON, and the data
    MGTools does not decode as `.bin` files
  - Refuse on import what the game cannot show, naming each string and the reason: characters without a glyph, words,
    lines and pages longer than the message window, and Metal Gear's HUD labels outside its HUD font
- **GCX scripts (`gcx`)**
  - Export a script's code and resources as a GCL listing to read and edit, and compile it back
  - Name more strcodes in the listing from a dictionary file, skipping with a warning the lines whose names would not
    compile back to their code
  - Export the UTF-8 texts of a Bluepoint script to a translation document, with the PS2 text as a note where it differs
  - Export the script's glyphs as a PNG image
- **String tables (`stov`)**: decrypt `stovc.bin` and `stovk.bin` to translation documents, and build and encrypt them
  back from the units of the document
- **Textures (`ctxr`)**: convert a texture's full-size level to a PNG image and back, keeping the alpha as stored and
  remaking the mipmaps, colour range and alpha flag as the game's converter did; one texture, a folder or a wildcard
  pattern at a time
- **2D layouts (`la2`)**: edit the node tree, items, animations, sprites, colours and fonts of a HUD or menu as JSON,
  with each text checked against the glyphs of its font
- **Sprite atlases (`tri`)**: edit each sprite's GS registers as JSON, with its texture coordinates derived from them
- **Console font (`cfon`)**: edit the glyph boxes and the glyph of each character as JSON
- **TNOF fonts (`tnof`)**: export a font as a greyscale PNG image per glyph and JSON of the metrics, and import changed
  and added glyphs
- **Keepfonts (`keepfont`)**: export a PNG image per Latin glyph, one of the kana and JSON of the flags, and import
  glyphs as wide as their images
- **Sound banks (`sdx`)**: unpack the sound effects of a stage to SPU-ADPCM waves, MIDI files and JSON, and pack them
  back, also with waves and MIDI files of another size
- **Game files (`files`)**: list which file the Master Collection reads for each line of its file lists, for any
  language, region and controller
- **All commands**: never replace an exported file or folder that may hold edits, and keep the first file an import
  replaces as `.orig`

Not covered: the Unity launcher of the Master Collection (`launcher.exe`, `launcher_Data`), the executables and
libraries (`MetalGear.exe`, `settings.exe`, `METAL GEAR.exe`, `Engine.dll`, `mg1.dll`, `mg2.dll`), audio codecs (the
waves stay SPU-ADPCM, the `.sdt` music and voice streams are not read), shaders and icons (`.ico`).

Requirements
------------

- Python 3.14+ (the portable builds include it)

Installing
----------

Download the portable build for your system from the [Releases](https://github.com/GrzybDev/MGTools/releases) page:
`MGTools_v<version>_Windows.exe` (code-signed), `MGTools_v<version>_Linux` or `MGTools_v<version>_macOS`. Each is a
single executable that needs no Python; run it in place of `mgtools` in the commands below, on Linux and macOS after
making it executable with `chmod +x`. The macOS build is not notarised, so macOS keeps a copy downloaded with a browser
from running until its quarantine flag is cleared with `xattr -d com.apple.quarantine MGTools_v<version>_macOS`.

To install the command with Python instead, give pipx or uv the repository's URL:

```sh
pipx install git+https://github.com/GrzybDev/MGTools
```

`uv tool install` takes the same URL.

Usage
-----

The `mgtools` command has a group of commands for each kind of file, and the `files` command. `--help` lists them,
and after any group or command it shows what that takes:

```sh
mgtools --help
mgtools resource export --help
```

`python -m mgtools` runs the same commands in a Python environment the package is installed in, and `uv run mgtools`
in a clone of the repository.

Each group has an `export` and an `import` command, and `resource` also has `info`. Every output argument is optional.
Without one, a command writes next to its input, named after it: the exports of resource files, scripts, TNOF fonts,
keepfonts and sound banks create a folder, the other exports a file with the extension of what they write, and the
imports a file with the extension of the game file (`.raw` for resource files, TNOF fonts and keepfonts).

`--format` picks the format of the texts for translation that `resource export`, `gcx export` and `stov export` write:
`xliff-2.0` (`.xlf`, the default), `xliff-1.2` (`.xliff`) or `po`. Imports tell the formats apart by their content,
and untranslated units keep the original text. [Translation documents](#translation-documents) describes what each
format holds.

Exports never replace a file that may hold edits: when the file to write exists, the folder to write is not empty, or
the settings JSON that a texture export writes next to its PNG image exists, the export names it, writes nothing and
stops. Move it away or choose another output. A texture export into a folder checks only the files it writes there.

Imports replace their output. The first time one replaces a file, it keeps that file beside the new one as
`<name>.orig`, such as `english.raw.orig`, and prints `Kept the original as ...`. Once the `.orig` file exists, imports
replace the output without another copy. Rename the `.orig` file back to restore the original.

Every file is written through a temporary file in the same folder, so a failed import leaves the file it would replace
as it was. A command that fails prints the reason to the standard error and exits with code 1, or with code 2 when an
argument or option is missing or invalid.

### Resource files

```sh
mgtools resource info path/to/english.raw
mgtools resource export path/to/english.raw [path/to/output_dir] [--format xliff-2.0] [--charmap path/to/font.json] [--separate-glyphs]
mgtools resource import path/to/english [path/to/english.raw]
```

`info` names the game, Metal Gear or Metal Gear 2: Solid Snake, and lists what each section holds with its number of
leaves and its size in bytes.

`export` writes a resource file to a new or empty folder, by default next to the file and named after it: its texts
for translation, its font, pictures, palettes and sprite rectangles, and the data MGTools does not decode as `.bin` files (see
[Resource folders](#resource-folders)). It tells Metal Gear from Metal Gear 2, and a Japanese file from a European one,
by the file itself.

`import` builds a resource file from such a folder, by default next to the folder with the `.raw` extension. GOG's
files end in `.bin`, so name the output for them: `mgtools resource import English English.bin`. The folder holds one
translation document, in any of the three formats. Import refuses texts the game cannot show and names each of them
with the reason (see [Translating the games](#translating-the-games)).

The game files store no names for the letters a translation adds to the fonts. To export a translated file again, give
it the `font.json` of the folder it was imported from with `--charmap`.

`--separate-glyphs` saves each glyph of the font as its own image, named after its character, in a folder per page
instead of an image per page: `font/page0/U+0041.png` holds the `A` of page 0. `font.json` names the image of each
glyph, and `import` reads the font in whichever form `font.json` gives (see
[MSX fonts](docs/msx-font.md#separate-glyph-images)).

|                    Option | Description                                                                                | Default                              |
|--------------------------:|--------------------------------------------------------------------------------------------|--------------------------------------|
|          `--format`, `-f` | The format of the texts to translate: `xliff-2.0` (`.xlf`), `xliff-1.2` (`.xliff`) or `po` | `xliff-2.0`                          |
|               `--charmap` | The `font.json` of an earlier export, whose charmap names the characters of the codes      | the characters the game shipped with |
| `--separate-glyphs`, `-s` | Save each glyph of the font as its own image instead of an image per page                  | off                                  |

```sh
mgtools resource info English.bin
mgtools resource export English.bin
mgtools resource import English English.bin
```

The first command prints `Metal Gear, 77 sections` and a table of the sections. The second writes the folder
`English/`. The third builds `English.bin` from the folder and keeps the file it replaces as `English.bin.orig`.

### GCX scripts

```sh
mgtools gcx export path/to/00180720.gcx [path/to/output_dir] [--format xliff-2.0] [--source-language en] [--dictionary path/to/names.txt]
mgtools gcx import path/to/00180720 [path/to/00180720.gcx]
```

`export` writes a script to a folder, by default next to it and named after it: the listing of its code and resources,
the UTF-8 texts of a Bluepoint script as a translation document, a unit `res:N` per string, and its glyphs (see
[GCX folders](#gcx-folders)). `--source-language` names the language of the texts in XLIFF documents; PO has no field
for it. The scripts of the `fr` folder hold the French and the English texts: the listing shows which resources
(`res:N`) each language uses. Button icons are private-use characters, which translation tools may show as nothing; a
note names those of each unit.

The listing writes a strcode as its name where MGTools knows one, else as `#` and six hex digits. `--dictionary` gives
it more names: a text file with a strcode in hex and a name on each line, such as `379210 lamp`. Its names replace the
built-in ones of the same codes, and words after a name are ignored. Import compiles each name back to its strcode
and needs no dictionary, so export skips a dictionary line that would not compile back to its code and warns with the
number of skipped lines and the line number and reason of the first three (see
[Strcode dictionaries](docs/gcx.md#strcode-dictionaries)).

`import` compiles the folder back, by default next to it with the `.gcx` extension. The translation document must hold
a unit for each string and no other, and `glyphs.png` must have the size that the number of glyphs in the listing
gives.

|                    Option | Description                                                                                | Default            |
|--------------------------:|--------------------------------------------------------------------------------------------|--------------------|
|          `--format`, `-f` | The format of the texts to translate: `xliff-2.0` (`.xlf`), `xliff-1.2` (`.xliff`) or `po` | `xliff-2.0`        |
| `--source-language`, `-l` | The language of the texts as a BCP 47 tag, written to XLIFF documents                      | `en`               |
|            `--dictionary` | A text file of strcodes and their names, whose names the listing writes for those codes    | the built-in names |

```sh
mgtools gcx export 00180720.gcx --format po
mgtools gcx import 00180720
```

The first command writes `00180720/script.gcl`, `00180720/text.po` and, for a script with glyphs,
`00180720/glyphs.png`. The second builds `00180720.gcx` from the folder and keeps the original as `00180720.gcx.orig`.

### String tables

```sh
mgtools stov export path/to/stovc.bin [path/to/stovc.xlf] [--format xliff-2.0]
mgtools stov import path/to/stovc.xlf [path/to/stovc.bin]
```

`export` decrypts a table to a translation document, by default next to it with the extension of the format. Each
string is a unit named after its id and language, such as `000e66b2.en`; the units mix the table's languages, and the
document gives English as its source language.

`import` builds the table from the units of the document alone, by default next to the document with the `.bin`
extension: a unit removed from the document removes its string. A table is encrypted with its name up to the first
dot, so the output must be named `stovc` or `stovk` up to its first dot; import refuses any other name.

|           Option | Description                                                                                | Default     |
|-----------------:|--------------------------------------------------------------------------------------------|-------------|
| `--format`, `-f` | The format of the texts to translate: `xliff-2.0` (`.xlf`), `xliff-1.2` (`.xliff`) or `po` | `xliff-2.0` |

```sh
mgtools stov export stovc.bin --format po
mgtools stov import stovc.po
```

The first command writes `stovc.po`. Once it is translated, the second builds `stovc.bin` from it and keeps the table
it replaces as `stovc.bin.orig`.

### Textures

```sh
mgtools ctxr export path/to/texture.ctxr [path/to/texture.png]
mgtools ctxr export path/to/textures_dir [path/to/output_dir]
mgtools ctxr export "path/to/textures/*.ctxr" [path/to/output_dir]
mgtools ctxr import path/to/texture.png [path/to/texture.ctxr]
mgtools ctxr import path/to/images_dir [path/to/output_dir]
mgtools ctxr import "path/to/images/*.png" [path/to/output_dir]
```

`export` writes a texture's full-size level as an RGBA PNG image, with the alpha as stored, and its settings as JSON
of the same name next to it. `import` reads both and builds the texture at the size of the image, remaking its
mipmaps, colour range and alpha flag as the game's converter did. Many textures use the PS2 alpha scale, where 128 is
opaque; the alpha is never rescaled.

In place of one file, both commands take a folder or a wildcard pattern and convert every texture it names:

- A folder: `export` converts each `.ctxr` file in it, and `import` each `.png` image with its settings `.json` beside
  it. Files in its subfolders are left out.
- A pattern: `*` stands for any part of a name, `?` for one character, `[...]` for one of the characters listed and
  `**` for any number of folders, as in `textures/**/*.ctxr`. Everything it matches must be a `.ctxr` file for
  `export`, or a `.png` image with its `.json` beside it for `import`, and a file it matches by several paths, as
  `textures/*/../*.ctxr` can, is converted once. MGTools expands the pattern itself, as PowerShell and cmd pass it on
  unchanged; in bash, zsh and other POSIX shells, put it in quotes, as they would expand it first. A path that exists
  is always read as a path, never as a pattern.

The output of a folder or pattern is a folder. Without one, each file is written next to its input. With one, the
files keep their layout below the folder or below the part of the pattern before its first wildcard: with the pattern
`textures/**/*.ctxr` and the output `out`, `textures/flatlist/_win/x.ctxr` is exported to `out/flatlist/_win/x.png`.
Every texture is read and converted, and every file an export would write is checked, before anything is written, so
one texture that cannot be converted stops the command with nothing written. Each converted file gets a line of its
own. A folder without textures, a pattern that matches nothing or a file of another kind, an output that is a file
and an output that two textures would be written to are refused before anything is read. So is an output of one
texture with the extension of its input, such as `b.png` in `mgtools ctxr import a.png b.png`, which is what a POSIX
shell passes for an unquoted pattern that matches two images.

```sh
mgtools ctxr export console.ctxr
mgtools ctxr import console.png
```

The first command writes `console.png` and `console.json`. The second builds `console.ctxr` from them and keeps the
original as `console.ctxr.orig`.

```sh
mgtools ctxr export "textures/**/*.ctxr" textures_png
mgtools ctxr import "textures_png/**/*.png" textures
```

Run from the game's folder, the first command writes the textures of `textures/` as PNG images and JSON files in
`textures_png/`, such as `textures_png/flatlist/_win/000237d1.png`. Once they are edited, the second builds each
texture back in its place in `textures/` and keeps each texture it replaces as `<name>.orig`.

### 2D layouts

```sh
mgtools la2 export path/to/memcard.la2 [path/to/memcard.json]
mgtools la2 import path/to/memcard.json [path/to/memcard.la2]
```

`export` writes a layout as JSON, with its texts in Latin-1 and its offsets replaced by indices. `import` computes the
counts, sizes and offsets again, so a text may change length, and refuses a text whose font has no glyph for one of
its characters.

```sh
mgtools la2 export memcard.la2
mgtools la2 import memcard.json
```

The first command writes `memcard.json`. The second builds `memcard.la2` from it and keeps the original as
`memcard.la2.orig`.

### Sprite atlases

```sh
mgtools tri export path/to/atlas.tri [path/to/atlas.json]
mgtools tri import path/to/atlas.json [path/to/atlas.tri]
```

`export` writes each sprite's strcode and GS registers as JSON. `import` derives each sprite's texture coordinates
from its TEX0 and CLAMP registers, so a changed clamp rectangle moves or resizes the sprite on its page.

```sh
mgtools tri export scope_0_stage_r_sna01_r.tri
mgtools tri import scope_0_stage_r_sna01_r.json
```

The first command writes `scope_0_stage_r_sna01_r.json`. The second builds `scope_0_stage_r_sna01_r.tri` from it and
keeps the original as `scope_0_stage_r_sna01_r.tri.orig`.

### Console font

```sh
mgtools cfon export path/to/console.cfon [path/to/console.json]
mgtools cfon import path/to/console.json [path/to/console.cfon]
```

`export` writes the glyph boxes of the font and the glyph of each character as JSON. The glyphs are drawn in
`EngineSupport/Fonts/_win/console.ctxr`: to give a character a glyph of its own, draw it in that texture with
[`mgtools ctxr`](#textures), add its box to `glyphs` and map the character to the new index.

```sh
mgtools cfon export console.cfon
mgtools cfon import console.json
```

The first command writes `console.json`. The second builds `console.cfon` from it and keeps the original as
`console.cfon.orig`.

### TNOF fonts

```sh
mgtools tnof export path/to/MGS_Font.raw [path/to/output_dir]
mgtools tnof import path/to/MGS_Font [path/to/MGS_Font.raw]
```

`export` writes a font to a folder, by default next to it and named after it. `import` takes the size of each glyph
from its image and sorts the glyphs by code point, so a row added to `font.json` with its image adds a glyph. The
engine draws with a font built into `METAL GEAR.exe`, and `EngineSupport/Fonts/MGS_Font.raw` does not appear to be
used (see [Known limitations](#known-limitations)); [TNOF fonts](docs/tnof.md#the-built-in-font) shows how to extract
the font it draws with.

```sh
mgtools tnof export MGS_Font.raw
mgtools tnof import MGS_Font
```

The first command writes `MGS_Font/font.json` and an image per glyph, such as `MGS_Font/glyphs/U+0041.png`. The second
builds `MGS_Font.raw` from the folder and keeps the original as `MGS_Font.raw.orig`.

### Keepfonts

```sh
mgtools keepfont export path/to/keepfont.raw [path/to/output_dir]
mgtools keepfont import path/to/keepfont [path/to/keepfont.raw]
```

`export` writes a keepfont to a folder, by default next to it and named after it. `import` makes each Latin glyph as
wide as its image, 1 to 64 pixels, and 24 pixels high.

```sh
mgtools keepfont export keepfont_stage_r_sna01_r.raw
mgtools keepfont import keepfont_stage_r_sna01_r
```

The first command writes `keepfont_stage_r_sna01_r/keepfont.json`, an image per Latin glyph, such as
`keepfont_stage_r_sna01_r/latin/41.png` for `A`, and `keepfont_stage_r_sna01_r/kana.png`. The second builds
`keepfont_stage_r_sna01_r.raw` from the folder and keeps the original as `keepfont_stage_r_sna01_r.raw.orig`.

### Sound banks

```sh
mgtools sdx export path/to/pk0001a1.sdx [path/to/output_dir]
mgtools sdx import path/to/pk0001a1 [path/to/pk0001a1.sdx]
```

`export` unpacks a sound bank file to a folder, by default next to it and named after it. `import` rebuilds the sizes,
offsets and block counts, so a wave or a MIDI file may change size.

```sh
mgtools sdx export pk0001a1.sdx
mgtools sdx import pk0001a1
```

The first command writes `pk0001a1/sdx.json`, the waves of each bank, such as `pk0001a1/bank0/waves/000.adpcm`, and
its sound effects, such as `pk0001a1/bank0/sounds/0000.mid`. The second builds `pk0001a1.sdx` from the folder and
keeps the original as `pk0001a1.sdx.orig`.

### Game files

```sh
mgtools files "path/to/MG and MG2" [--language en] [--region eu] [--controller xbox] [--keyboard-layout a]
```

`files` reads the file lists of an install of METAL GEAR & METAL GEAR 2: Solid Snake and prints the data folder, then
each list with, per line, the id of the file and the file the engine reads for it. A line whose file exists nowhere
is shown as `missing`, and a warning at the end counts such lines. The command only reads the install.

|               Option | Description                                                                 | Default                      |
|---------------------:|-----------------------------------------------------------------------------|------------------------------|
|   `--language`, `-l` | The game's language: `en`, `jp`, `fr`, `gr`, `it`, `pr`, `sp`, `du` or `ru` | `en`                         |
|     `--region`, `-r` | The game's region: `us`, `jp` or `eu`                                       | `jp` for Japanese, else `eu` |
| `--controller`, `-c` | The controller type: `ps5`, `ps4`, `xbox`, `nx`, `stmd` or `kbd`            | `xbox`                       |
|  `--keyboard-layout` | The keyboard layout setting of the `kbd` controller: `a` or `b`             | `a`                          |

```sh
mgtools files "path/to/MG and MG2" --language fr
```

The command prints `Data folder: fr` and the lists of that folder, among them:

```text
fr/stage/mg1/manifest.txt
  cache/00861cbc.raw  fr/stage/mg1/cache/ovr_stm/french.raw
```

French Metal Gear therefore reads its resources from `fr/stage/mg1/cache/ovr_stm/french.raw`.

### Translating the games

1. Find the file the game reads: on GOG `Resource\<language>.bin`, in the Master Collection the one `mgtools files`
   names (see [Files the games read](#files-the-games-read)).
2. Export it to a folder of your own:

   ```sh
   mgtools resource export "path/to/MG and MG2/fr/stage/mg1/cache/ovr_stm/ovr_eu/english.raw" mg1 --format po
   ```

3. Translate `mg1/text.po` in a translation tool. Each string is a unit named after its block and number, such as
   `mg1.b03.e000`. Its notes say where the game shows it, how many bytes the original takes and which limits apply.
   Keep placeholders such as `{wait}` or `{btn:1}`; untranslated units keep the original text.
4. Give each letter the font lacks a code: name it in the `charmap` of `mg1/font.json` at a code the charmap does not
   use (`7F`, `A0` to `DF`; the European releases leave `A0` to `A6`, `AE` and `AF` free) or instead of a letter the
   translation does not need. Give the code a width in the `widths` of page 0, the font of the texts, and draw the
   glyph in `mg1/font/page0.png`: each code has a cell 64 pixels wide and as high as the page, 16 a row from code `20`,
   and the glyph takes the first columns of it, in the four greys of the image. In a folder exported with
   `--separate-glyphs`, draw the glyph instead as an image of its own in `mg1/font/page0/`, as wide as its width and 24
   pixels high, and name the image in the `images` of page 0.
5. Metal Gear draws its HUD and menu labels (`mg1.b15.e003` to `e008`, `e013` to `e015` and `e141`) with an 8 × 8
   sprite font of capitals, digits and the codes `B0` to `DF`, 8 pixels a character. Letters beyond A to Z in these
   labels need a code from `B0` to `DF`, and a glyph in `mg1/images/62.000.png`, whose 8 × 8 cells go 16 a row from
   code `B0`.
6. Import the folder and put the new file in place of the one the game reads:

   ```sh
   mgtools resource import mg1 english.raw
   ```

7. Translate the texts around the games the same way: the scripts with [`mgtools gcx`](#gcx-scripts), the string
   tables with [`mgtools stov`](#string-tables) and the texts of the layouts in the JSON of
   [`mgtools la2`](#2d-layouts), within the letters their fonts can draw (see [Known limitations](#known-limitations)).

Japanese texts take double-byte characters too: a character the font lacks needs to be listed in the `double_byte` of
`font.json` and drawn in `font/page4.png`, or with `--separate-glyphs` drawn as a 24 × 24 image in `font/page4/` and
named in `double_byte_images`.

Import refuses what the engine cannot show:

- The game finds each string by its position: units cannot be added or removed.
- Metal Gear's message window takes 48 bytes a line, wrapped at spaces, and a blank line starts a page.
- Metal Gear 2's takes 45 bytes a line and 10 lines a page; `{wait}` and `{autowait}` start a page. The opening story
  and the credits are laid out freely.
- Japanese lines are never wrapped and take 48 (Metal Gear) or 47 bytes (Metal Gear 2). In Metal Gear 2, `{wait}`
  hides the byte after it, so a line break or a space follows it.
- Every character needs a glyph: on page 0 for single bytes, on page 4 for double-byte characters.
- RGB copies of pictures can only use colours of their palette, and sprite rectangles go up to 255 pixels.

Menu strings are not wrapped either: keep them about as wide as the original, whose width in pixels their note gives.
[MSX texts](docs/msx-text.md) gives every rule.

### Known limitations

- The engine draws the UTF-8 texts of the scripts and string tables with a TNOF font built into `METAL GEAR.exe`;
  `EngineSupport/Fonts/MGS_Font.raw` does not appear to be used. The built-in font has no Polish letters but Ó and ó,
  and MGTools does not patch executables. Layouts store Latin-1 texts, which lack them too.
- Metal Gear's pause menu items are inside the script of section 71 of its resource file, which MGTools does not
  decode.
- Metal Gear 2's sprite fonts are not mapped, so its HUD labels are not checked like Metal Gear's.
- Import does not check that a script or string table keeps its button icons.
- A texture's PNG image saved without alpha imports as fully opaque.

File formats
------------

The formats of the games' own files are described in `docs/`:

| Page                                       | Covers                                                                                    |
|--------------------------------------------|-------------------------------------------------------------------------------------------|
| [MSX resource files](docs/msx-resource.md) | The node tree of the resource files, the sections of each game and the resource folder    |
| [MSX texts](docs/msx-text.md)              | Text blocks, string records, the character set, placeholders and the limits import checks |
| [MSX fonts](docs/msx-font.md)              | The five font pages, how glyphs are packed, and `font.json`                               |
| [MSX graphics](docs/msx-graphics.md)       | Palettes, pictures, screens, the colours the games show and the frame rectangles          |
| [GCX scripts](docs/gcx.md)                 | The script file, GCL bytecode, the PS2 text encoding, strcodes and the listing            |
| [String tables](docs/stov.md)              | The encryption, the table and its translation units                                       |
| [Textures](docs/ctxr.md)                   | The texture file, its versions, how the mipmaps are made and the settings JSON            |
| [2D layouts](docs/la2.md)                  | The header, node tree, items, animations, sprites, colours and fonts, and their JSON      |
| [Sprite atlases](docs/tri.md)              | The sprite entries, their GS registers and texture coordinates                            |
| [Console font](docs/cfon.md)               | The glyph boxes and the arrays that map characters to them                                |
| [TNOF fonts](docs/tnof.md)                 | The glyph table and records, and the font built into `METAL GEAR.exe`                     |
| [Keepfonts](docs/keepfont.md)              | The glyph table, the 2-bit Latin and kana glyphs                                          |
| [Sound banks](docs/sdx.md)                 | The banks and their chunks, waves and sound effect records                                |
| [File lists](docs/manifest.md)             | The lines of the lists, the data folders and how the engine picks the file it reads       |

### Translation documents

A unit per string, named by an id that tells import where its text belongs, with notes on how the game shows it.
Placeholders are plain text, never inline codes, as OmegaT 6.1 numbers the third and later inline codes of a segment
wrongly. Those of the MSX games: `{wait}` and `{autowait}` (wait for a button or half a second, then clear the window),
`{r}` and `{s}` (the speaker), `{e}`, `{f}`, `{speed:N}`, `{bgm:NN}`, `{se:NN}`, `{btn:N}` (a controller button), and
`{x:HH}` and `{sjis:HHHH}` for bytes that are no character.

- **XLIFF 2.0 and 1.2**: a unit (`trans-unit`) per string with its notes. A non-empty target is used whatever its
  state, since OmegaT marks none in XLIFF 2.0, and segments a tool split are joined back.
- **PO**: the id is the context and the notes are `#.` comments. Lines are never wrapped; fuzzy translations are not
  used.

OmegaT 6.1 hands every `.xlf` and `.xliff` file to its legacy XLIFF filter, which only translates existing targets. In
*Project > Properties... > Local File Filters...*, tick *Use local file filter settings* and untick *XLIFF (legacy
filter)*, or untick it for every project in *Options > Global File Filters...*.

### Resource folders

| Path                | Contents                                                                                   |
|---------------------|--------------------------------------------------------------------------------------------|
| `resource.json`     | The game, the containers without leaves and the indices of colours several indices show    |
| `text.xlf`          | The strings for translation (`text.xliff` or `text.po` in the other formats)               |
| `text.json`         | Metal Gear's style byte of each string and debug warp points; Metal Gear 2's string counts |
| `text/bNN.bin`      | The text blocks that hold no strings                                                       |
| `font.json`         | The charmap and the layout of the five font pages                                          |
| `font/pageN.png`    | The glyphs of each page                                                                    |
| `font/pageN/*.png`  | With `--separate-glyphs`, instead of `font/pageN.png`: an image per glyph of the page      |
| `images/SS.NNN.png` | The pictures, named by section and number                                                  |
| `palettes.json`     | The palettes, as lists of `#rrggbb`                                                        |
| `actors.json`       | Metal Gear: the rectangles of the actors' frames in the sprite sheets                      |
| `cells.json`        | Metal Gear 2: the cell atlas of the sprite sheets                                          |
| `raw/SS.NNN.bin`    | Everything else, named by its position in the file                                         |

- `font.json`: `charmap` gives the character of each code from `7F` and `A0` to `DF` that has one. Pages 0 to 3 (24,
  12, 18 and 24 pixels high) give the `widths` of their glyphs, from 1 to 64 pixels; `floor_packed` marks a page whose
  glyphs drop their last two pixels, which the engine draws from the next glyph, and `v` and `pad_bits` keep the bytes
  the Japanese pages and some glyphs carry. `double_byte` lists the characters of page 4's 24 × 24 glyphs in order.
  With `--separate-glyphs`, each page names its folder in `glyphs` and the image of each glyph by code in `images`,
  and `double_byte_glyphs` and `double_byte_images` do the same for page 4; a glyph without a character is named after
  its code, such as `code-FF.png`, and a glyph of page 4 without a code is `fallback.png` (glyph 0) or `unused-N.png`
  (glyph N; see [MSX fonts](docs/msx-font.md#separate-glyph-images)).
- Pictures are indexed PNG images whose palette holds the colours the game shows, index 0 transparent and every unused
  index a colour of its own. Import takes the indices of such images as they are, and maps the colours of RGB and RGBA
  copies back to indices (alpha 0 to index 0). Metal Gear 2 changes palettes as the screen does, so its pictures show
  the colours of where they are drawn. The two screens of each game are RGB PNG images.

### GCX folders

- `script.gcl`: the listing of the code and the resources. Statements end with a semicolon; whitespace and `//`
  comments are free. Strings are in the PS2 text encoding, with codes it has no character for in hex between braces,
  such as `{8C01}` for the first glyph.
- `text.xlf`: the UTF-8 text of each string of a Bluepoint script, as unit `res:N`, with the PS2 text as a note where
  it differs.
- `glyphs.png`: the script's glyphs, 24 × 24 pixels, 16 a row.

### Engine files

- **Textures**: an RGBA PNG image of the full-size level, with the alpha as stored, and JSON of the version, whether the texture has mipmaps and the texels the game's converter
  rounded otherwise.
- **Layouts**: JSON of the node tree, the items, the animations, the sprites, the colours and the fonts. Items and
  animations are named by their index from 0; node parents and the sprite and font of an item keep the file's indices
  from 1.
- **Sprite atlases**: JSON of each sprite's strcode and GS registers; texture coordinates follow from TEX0 and CLAMP.
- **Console font**: JSON of the glyph boxes in its texture and the glyph of each character.
- **TNOF fonts**: `font.json` with the metrics of each glyph and a greyscale image per glyph in `glyphs/U+XXXX.png`.
- **Keepfonts**: `keepfont.json` with the flags of each Latin glyph (codes `0x20` to `0xFF` in the Mac OS Roman
  layout), its image in `latin/XX.png`, 24 pixels high, and the kana in `kana.png`.
- **Sound banks**: `sdx.json` of the banks, waves and sound effects; per bank the waves as `waves/NNN.adpcm`, a MIDI
  file per sound effect in `sounds/` and the other chunks as `.bin` files.

Development
-----------

```sh
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
```

The tests on the game files export and import every file of each format and expect the very same bytes.
`MGTOOLS_STEAM_DIR` names the install of METAL GEAR & METAL GEAR 2: Solid Snake and `MGTOOLS_GOG_DIR` that of Metal
Gear on GOG; the tests of a release are skipped while its variable is unset. They only read the game folders and write
to pytest's temporary folders:

```sh
MGTOOLS_STEAM_DIR="path/to/MG and MG2" MGTOOLS_GOG_DIR="path/to/Metal Gear" uv run pytest
```

Credits
-------

- [GrzybDev](https://grzyb.dev)

Special thanks to:
- Konami (for making the games)
