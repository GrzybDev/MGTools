# File lists

The Master Collection's engine loads the files of each stage and slot page from file lists: `manifest.txt`, and
`bp_assets.txt` for textures, in the data folder of the game's language and region, such as
`fr/stage/mg1/manifest.txt`. For each line it reads one file, picked among override folders for the region and the
controller; the other copies of that file are never read. The string tables and the sound banks are not named in
any list. [`mgtools files`](../README.md#game-files) lists the file the game reads for each line; MGTools reads the
lists and never writes them.

Lines
-----

A list is UTF-8 text with one file per line and comma-separated columns:

| Column | Description                                                                      |
|--------|----------------------------------------------------------------------------------|
| 1      | Path of the file, from the game folder, such as `fr/stage/mg1/cache/english.raw` |
| 2      | Console path of the file; MGTools does not use it                                |
| 3      | Id the engine knows the file by, such as `cache/00180720.gcx`                    |
| 4      | Optional video mode                                                              |

The engine loads a line without a fourth column or with `60HZ` in it, and skips lines of other video modes (such as
`50HZ`) and empty lines. MGTools refuses a line with fewer than three columns, naming the list and the line number.

Data folder
-----------

The engine takes its lists from `<data folder>/<group>/<name>/`, two folder levels below the data folder, such as
`fr/stage/mg1/` or `fr/slot/memcard/`. The data folder follows the language and region the launcher passes:

| Region | Language                          | Data folder |
|--------|-----------------------------------|-------------|
| `jp`   | any                               | `jp`        |
| other  | `en` (English), `fr` (French)     | `fr`        |
| other  | `gr` (German)                     | `gr`        |
| other  | `it` (Italian)                    | `it`        |
| other  | `sp` (Spanish)                    | `sp`        |
| other  | `jp` (Japanese), `pr`, `du`, `ru` | `us`        |

The launcher passes the language with `-lan` (`en`, `jp`, `fr`, `gr`, `it`, `pr`, `sp`, `du`, `ru`), the region with
`-region` (`us`, `jp` or `eu`; the launcher passes `jp` for Japanese and `eu` for the other languages) and the
controller with `-ctrltype`:

| Controller    | Code   | Controller folder                                                                  |
|---------------|--------|------------------------------------------------------------------------------------|
| PlayStation 5 | `ps5`  | `ctrltype_ps5`                                                                     |
| PlayStation 4 | `ps4`  | `ctrltype_ps4`                                                                     |
| Xbox          | `xbox` | `ctrltype_xs`                                                                      |
| Switch        | `nx`   | `ctrltype_nx`                                                                      |
| Steam Deck    | `stmd` | `ctrltype_stmd`                                                                    |
| Keyboard      | `kbd`  | `ctrltype_kbd`; the keyboard layout setting adds `ctrltype_kbd/type_a` or `type_b` |

Finding the file
----------------

For each line, the engine starts from the path of the first column:

1. A line of `bp_assets.txt` names a texture: `_win/` goes before the file name, so
   `textures/flatlist/00abcdef.ctxr` becomes `textures/flatlist/_win/00abcdef.ctxr`.
2. A path that holds `.gcx` names a script: when `_bp/` before the file name gives a file that exists, the engine reads
   from that `_bp` folder (the [Bluepoint copy](gcx.md)). Only that file decides it; overrides of the plain copy are
   then not tried, and overrides inside `_bp` count only when `_bp` holds the file itself.
3. The engine tries the override folders below, from the most specific to the path itself, and reads the first file
   that exists.

| Order | Folder inserted                             | When          |
|-------|---------------------------------------------|---------------|
| 1     | `ovr_stm/ctrltype_kbd/type_<layout>/`       | Keyboard only |
| 2     | `ovr_stm/<controller folder>/ovr_<region>/` | Always        |
| 3     | `ovr_stm/<controller folder>/`              | Always        |
| 4     | `ovr_stm/ovr_<region>/`                     | Always        |
| 5     | `ovr_stm/`                                  | Always        |
| 6     | `ovr_<region>/`                             | Always        |
| 7     | none: the path itself                       | Always        |

The folders go right before the file name, or before the `_win` folder of a texture. A file at the top of the game
folder takes them at the top: `top.raw` becomes `ovr_eu/top.raw`. For `fr/stage/mg1/cache/english.raw` in the region
`eu` with the keyboard and layout B, the engine tries:

```text
fr/stage/mg1/cache/ovr_stm/ctrltype_kbd/type_b/english.raw
fr/stage/mg1/cache/ovr_stm/ctrltype_kbd/ovr_eu/english.raw
fr/stage/mg1/cache/ovr_stm/ctrltype_kbd/english.raw
fr/stage/mg1/cache/ovr_stm/ovr_eu/english.raw
fr/stage/mg1/cache/ovr_stm/english.raw
fr/stage/mg1/cache/ovr_eu/english.raw
fr/stage/mg1/cache/english.raw
```

A texture `textures/flatlist/00abcdef.ctxr` is looked for in `textures/flatlist/ovr_stm/_win/00abcdef.ctxr` and so on,
down to `textures/flatlist/_win/00abcdef.ctxr`; the copy without `_win` is never read.

The files command
-----------------

[`mgtools files`](../README.md#game-files) prints the data folder, then each list from the game folder with, per line,
the id of the third column and the file the engine reads. A line whose file exists in none of the places is shown as
`missing` with its first column, and a warning at the end counts such lines. The region defaults to the one the launcher
passes: `jp` for Japanese, else `eu`.

Worked example
--------------

An invented game folder with two lists. `fr/stage/demo/manifest.txt`:

```text
fr/stage/demo/cache/english.raw,stage/demo/english.raw,cache/0a1b2c3d.raw
fr/stage/demo/cache/0abc1234.gcx,stage/demo/0abc1234.gcx,cache/0abc1234.gcx
fr/stage/demo/cache/intro.sdx,stage/demo/intro.sdx,cache/00c0ffee.sdx,50HZ
fr/stage/demo/cache/intro60.sdx,stage/demo/intro60.sdx,cache/00c0ffee.sdx,60HZ
```

`fr/slot/title/bp_assets.txt`:

```text
textures/flatlist/00abcdef.ctxr,title/logo.tex,fr/slot/title/cache/00abcdef.ctxr
```

The folder holds these files:

```text
fr/stage/demo/cache/english.raw
fr/stage/demo/cache/ovr_stm/ovr_eu/english.raw
fr/stage/demo/cache/0abc1234.gcx
fr/stage/demo/cache/_bp/0abc1234.gcx
fr/stage/demo/cache/_bp/ovr_stm/0abc1234.gcx
textures/flatlist/_win/00abcdef.ctxr
textures/flatlist/ovr_stm/ctrltype_ps5/_win/00abcdef.ctxr
```

`mgtools files path/to/game` (English, region `eu`, Xbox controller) prints:

```text
Data folder: fr
fr/slot/title/bp_assets.txt
  fr/slot/title/cache/00abcdef.ctxr  textures/flatlist/_win/00abcdef.ctxr
fr/stage/demo/manifest.txt
  cache/0a1b2c3d.raw  fr/stage/demo/cache/ovr_stm/ovr_eu/english.raw
  cache/0abc1234.gcx  fr/stage/demo/cache/_bp/ovr_stm/0abc1234.gcx
  cache/00c0ffee.sdx  missing (fr/stage/demo/cache/intro60.sdx)
Warning: 1 of 4 lines name a file that does not exist
```

The 50 Hz line is skipped, the resource file comes from `ovr_stm/ovr_eu/`, and the script from the override inside
`_bp`. With `--controller ps5`, the texture comes from `textures/flatlist/ovr_stm/ctrltype_ps5/_win/00abcdef.ctxr`
instead.
