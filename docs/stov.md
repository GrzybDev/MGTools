# String tables

The string tables hold texts of the Master Collection's engine in several languages, each string named by a 32-bit id.
The game has two: `EngineSupport/stovc.bin` for controllers and `EngineSupport/stovk.bin` for the keyboard. Both are
encrypted with a key derived from their file name. `mgtools stov export` decrypts a table to a translation document,
and `mgtools stov import` builds and encrypts it again (see [Usage](../README.md#string-tables)).

Every number is little-endian.

Encryption
----------

The whole file is XORed with a keystream of the MT19937 generator. The same operation encrypts and decrypts.

1. The key is the file's name without its folder, up to its first dot: `stovc` for `stovc.bin`, and also for
   `stovc.backup.bin`. A table renamed to `stovc_pl.bin` has the key `stovc_pl` and no longer decrypts.
2. The seed is computed from the bytes b of the key, starting from 0:

   ```
   seed = (seed × 0x2356F + b × 0x1D35) mod 2^32
   ```

3. The 624 words of the MT19937 state are filled from the seed by the original 1998 initialisation (`sgenrand`), not
   the later `init_genrand`:

   ```
   for each of the 624 words:
       high = seed & 0xFFFF0000
       seed = (69069 × seed + 1) mod 2^32
       word = high | (seed >> 16)
       seed = (69069 × seed + 1) mod 2^32
   ```

4. The keystream is the generator's 32-bit outputs from the first on, each written little-endian. Byte n of the file is
   XORed with byte n of the keystream; the last output is cut to the bytes the file has left.

| Key     | Seed       | First keystream bytes                           |
|---------|------------|-------------------------------------------------|
| `stovc` | 0x3DBD9257 | 7A EB 47 F6 D1 42 5F 31 6A C3 C7 F2 EF 80 3D 81 |
| `stovk` | 0x3DBE7BFF | 6F A2 22 52 59 5A E2 66                         |

For `stovc`, the seed goes through 0x000D1ECF (`s`), 0xFABC72C5 (`t`), 0xA10F3666 (`o`), 0x68B52AA8 (`v`) and
0x3DBD9257 (`c`), and the first outputs are 0xF647EB7A, 0x315F42D1, 0xF2C7C36A and 0x813D80EF.

Overall layout
--------------

Decrypted, a table is a header, the entries and the strings:

| Offset      | Size | Type | Description                                |
|-------------|------|------|--------------------------------------------|
| 0x00        | 8    | u64  | Size of the entries in bytes, 24 per entry |
| 0x08        | size |      | The entries, sorted by id                  |
| 0x08 + size | ...  |      | The strings                                |

Entry:

| Offset | Size | Type | Description                                         |
|--------|------|------|-----------------------------------------------------|
| 0x00   | 4    | u32  | Id of the string                                    |
| 0x04   | 4    | u32  | Language, from the table below                      |
| 0x08   | 8    | u64  | Offset of the string from the start of the strings  |
| 0x10   | 8    | u64  | Offset of the end of the string, after its NUL byte |

The strings are UTF-8, each ending with a NUL byte, stored back to back in the order of the entries with nothing after
the last. Line breaks are CRLF.

| Language | Name | Language | Name |
|----------|------|----------|------|
| 0        | all  | 4        | it   |
| 1        | jp   | 5        | gr   |
| 2        | en   | 6        | sp   |
| 3        | fr   |          |      |

The engine keeps the strings of language 0 (all) and those of the language it runs in.

Editable form
-------------

`mgtools stov export` writes a translation document with a unit per string, named by the id in eight lowercase hex
digits and the language, such as `000e66b2.en`. The units mix the table's languages; the document gives English as its
source language. Line breaks are LF in the document and become CRLF again on import.

`mgtools stov import` rebuilds the table from the units of the document alone: a unit removed from the document removes
the string from the table. A unit whose id is not eight lowercase hex digits, a dot and one of the language names is
refused. The key comes from the name of the output file, which therefore has to be `stovc` or `stovk` up to its first
dot.

Checks and refusals
-------------------

Reading a table, MGTools refuses:

- a size larger than the file, which is what a table decrypted under the wrong name gives;
- a size that is not a multiple of 24;
- ids that are not in increasing order, or repeat;
- a string that does not start where the one before it ends (the first at 0), or whose only NUL is not its last byte;
- a language above 6, and a string that is not UTF-8;
- bytes after the last string.

Writing a table, it sorts the strings by id and refuses two strings with one id, a string holding a NUL character, and
a file name whose key is not `stovc` or `stovk`, since the game reads no other table and the name is the key.

Worked example
--------------

An invented table with two strings, written as `stovc.bin`:

| Id         | Language | Text               |
|------------|----------|--------------------|
| 0x00001234 | all      | `Pause`            |
| 0x00001235 | en       | `Two` CRLF `lines` |

Decrypted, 0x49 bytes:

```text
0000  30 00 00 00 00 00 00 00 34 12 00 00 00 00 00 00
0010  00 00 00 00 00 00 00 00 06 00 00 00 00 00 00 00
0020  35 12 00 00 02 00 00 00 06 00 00 00 00 00 00 00
0030  11 00 00 00 00 00 00 00 50 61 75 73 65 00 54 77
0040  6F 0D 0A 6C 69 6E 65 73 00
```

| Offset | Bytes                              | Meaning                          |
|--------|------------------------------------|----------------------------------|
| 0x00   | `30 00 00 00 00 00 00 00`          | The entries take 0x30 bytes: two |
| 0x08   | `34 12 00 00`, `00 00 00 00`       | Id 0x00001234, language 0 (all)  |
| 0x10   | `00 ...`, `06 ...`                 | From 0 to 6 in the strings       |
| 0x20   | `35 12 00 00`, `02 00 00 00`       | Id 0x00001235, language 2 (en)   |
| 0x28   | `06 ...`, `11 ...`                 | From 6 to 0x11                   |
| 0x38   | `50 61 75 73 65 00`                | `Pause` and its NUL              |
| 0x3E   | `54 77 6F 0D 0A 6C 69 6E 65 73 00` | `Two`, CRLF, `lines` and the NUL |

Encrypted with the keystream of `stovc`:

```text
0000  4A EB 47 F6 D1 42 5F 31 5E D1 C7 F2 EF 80 3D 81
0010  92 DF 29 A4 7B 66 9E 49 AD 2B FF 28 4E 8F 9E B5
0020  15 F2 B9 D3 29 4E 25 FD D2 1A 18 01 68 2D C1 D6
0030  83 B9 72 ED 58 D2 06 19 15 E4 24 BE A4 6C 5E 16
0040  FE 89 50 A3 BE BE BF BB 28
```

The first byte is 0x30 XOR 0x7A = 0x4A. Exported, the table becomes the units `00001234.all` (`Pause`) and
`00001235.en` (`Two`, a line break, `lines`).
