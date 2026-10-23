# Sound banks

A sound bank file holds the sound effects of a stage of the Master Collection: waves in SPU-ADPCM, instrument tables and
a MIDI sequence per sound effect. The games read them from `us/stage/{mg1,mg2,r_sna01}/pk0*.sdx` (`jp/stage/...` in
Japanese). `mgtools sdx export` unpacks a file to a folder of JSON, waves and MIDI files, and `mgtools sdx import` packs
it back to the same bytes (see [Usage](../README.md#sound-banks)). MGTools does not decode the SPU-ADPCM waves or the
instrument tables; it keeps them as they are.

Every number is little-endian unless a table says otherwise.

Overall layout
--------------

| Part    | Description                                                               |
|---------|---------------------------------------------------------------------------|
| Banks   | One or more banks, back to back; a bank follows as long as `IPSQ` does    |
| Padding | Bytes the engine never reads, up to the end of the last 0x800-byte sector |

The file size is a multiple of 0x800, and the padding is shorter than 0x800 bytes.

### Chunks

A bank is a run of chunks, always in this order:

| Order | Tag    | Payload                                               |
|-------|--------|-------------------------------------------------------|
| 1     | `IPSQ` | The sizes of the bank and its memory slot, 0x38 bytes |
| 2     | `IWAV` | The wave table, 16 bytes per wave                     |
| 3     | `IA3P` | Instrument table, not decoded                         |
| 4     | `TPAT` | Instrument table, not decoded                         |
| 5     | `IPAT` | Instrument table, not decoded                         |
| 6     | `TSEQ` | The sound effect slots, 2048 × 4 bytes                |
| 7     | `ISEQ` | The sound effect records                              |
| 8     | `BVAG` | The resident waves                                    |
| 9     | `TERM` | Empty: the end of the resident part                   |
| 10    | `BPVG` | The streamed waves                                    |

Each chunk is:

| Offset | Size | Type    | Description         |
|--------|------|---------|---------------------|
| 0x00   | 4    | char[4] | Tag                 |
| 0x04   | 4    | u32     | Size of the payload |
| 0x08   | size |         | Payload             |

### IPSQ

| Offset | Size | Type | Description                                                                          |
|--------|------|------|--------------------------------------------------------------------------------------|
| 0x00   | 4    | u32  | Size of the resident part: the offset of the `TERM` chunk from the start of the bank |
| 0x04   | 4    | u32  | Size of the `BPVG` chunk, its 8-byte tag and size included                           |
| 0x08   | 2    | s16  | The sound memory slot the engine loads the bank into                                 |
| 0x0A   | 0x2E |      | Zeros                                                                                |

### IWAV

One entry per wave, numbered from 0:

| Offset | Size | Type | Description                                                                    |
|--------|------|------|--------------------------------------------------------------------------------|
| 0x00   | 4    | u32  | ADSR                                                                           |
| 0x04   | 4    | u32  | Bit 31 set: the wave is in `BVAG`, else in `BPVG`; bits 0-30: its offset there |
| 0x08   | 2    | u16  | Sample rate in Hz                                                              |
| 0x0A   | 2    | u16  | Number of 16-byte SPU-ADPCM blocks                                             |
| 0x0C   | 4    | u32  | A word whose meaning is not known, kept as it is                               |

A wave is 0x80 zero bytes followed by its blocks. The waves of each chunk, `BVAG` and `BPVG`, are stored back to back
in table order from offset 0 and fill the chunk.

### TSEQ

A u32 for each sound effect id from 0 to 2047:

| Value      | Meaning                                                                            |
|------------|------------------------------------------------------------------------------------|
| 0x00FFFFFF | No sound effect has this id                                                        |
| other      | Bits 24-31: flags, kept as they are; bits 0-23: the offset of the record in `ISEQ` |

### ISEQ

A record per sound effect:

| Offset | Size | Type | Description                                                                               |
|--------|------|------|-------------------------------------------------------------------------------------------|
| 0x00   | 16   |      | Header, kept as it is                                                                     |
| 0x10   | ...  |      | A standard MIDI file: `MThd` and as many `MTrk` chunks as it names, with big-endian sizes |
| ...    | 0-3  |      | Zeros to a multiple of 4 bytes                                                            |

The records follow each other from offset 0 in the order of their offsets; no two ids share one. MGTools finds the end
of each MIDI file from its `MThd` size, the track count in `MThd` and the size of each `MTrk`.

Editable form
-------------

Export writes into the folder:

| Path                                     | Contents                                                                                                                                                                                     |
|------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `sdx.json`                               | Per bank: its `slot`; per wave `sample_rate`, `resident` (in `BVAG`), `adsr` and `extra` (the word at 0x0C); per sound effect `id`, `flags` and `header` in hex, in the order of the records |
| `padding.bin`                            | The padding after the banks                                                                                                                                                                  |
| `bankN/IA3P.bin`, `TPAT.bin`, `IPAT.bin` | The instrument tables of bank N                                                                                                                                                              |
| `bankN/waves/NNN.adpcm`                  | The SPU-ADPCM blocks of each wave, without the 0x80 zero bytes before them                                                                                                                   |
| `bankN/sounds/NNNN.mid`                  | The MIDI file of each sound effect, named by its id                                                                                                                                          |

Import rebuilds the sizes, offsets and block counts from the files, so a wave or a MIDI file may change size. The
padding is cut or filled with zeros to end the last sector.

Checks and refusals
-------------------

Reading a file, MGTools refuses a chunk with an unexpected tag, an `IPSQ` chunk that is not 0x38 bytes ending in zeros,
sizes in `IPSQ` that do not match the bank, a `TERM` chunk with a payload, waves that are not stored back to back or do
not start with 0x80 zero bytes, a `TSEQ` chunk that is not 2048 slots, records shared by two ids or not starting at
offset 0, a record without a MIDI file or with other bytes than zeros after it, and data after the banks that does not
end the file within one sector.

Writing a file, it refuses a wave whose data is not whole 16-byte blocks or takes more than 65535 of them, a sample rate
outside 1 to 65535 Hz, a sound effect id above 2047 or used twice, flags above 255, a header that is not 16 bytes, MIDI
data that is not exactly one MIDI file, and records past the 16 MiB that `TSEQ` offsets reach.

Worked example
--------------

An invented file with one bank in slot 2, two waves and one sound effect. Wave 0 is resident, 22050 Hz, with 2 blocks;
wave 1 is streamed, 11025 Hz, with 1 block. Sound effect 3 has the flags 1, the header bytes 00 to 0F and a 26-byte
MIDI file with one empty track. Each instrument table is 4 zero bytes. The chunks:

| Offset | Tag    | Payload size | Contents                                             |
|--------|--------|--------------|------------------------------------------------------|
| 0x0000 | `IPSQ` | 0x38         | 70 21 00 00 98 00 00 00 02 00, then zeros            |
| 0x0040 | `IWAV` | 0x20         | Two entries                                          |
| 0x0068 | `IA3P` | 0x4          | 00 00 00 00                                          |
| 0x0074 | `TPAT` | 0x4          | 00 00 00 00                                          |
| 0x0080 | `IPAT` | 0x4          | 00 00 00 00                                          |
| 0x008C | `TSEQ` | 0x2000       | FF FF FF 00 for every id but 3, which is 00 00 00 01 |
| 0x2094 | `ISEQ` | 0x2C         | The record of sound effect 3                         |
| 0x20C8 | `BVAG` | 0xA0         | Wave 0: 0x80 zero bytes and 0x20 bytes of blocks     |
| 0x2170 | `TERM` | 0            |                                                      |
| 0x2178 | `BPVG` | 0x90         | Wave 1: 0x80 zero bytes and 0x10 bytes of blocks     |
| 0x2210 |        |              | Padding to 0x2800                                    |

`IPSQ` gives 0x2170, the offset of `TERM`, and 0x98, the 8 bytes of the `BPVG` header and its 0x90 bytes of payload.
The `IWAV` entries:

```text
FF 00 00 80  00 00 00 80  22 56  02 00  00 00 00 00
78 56 34 12  00 00 00 00  11 2B  01 00  07 00 00 00
```

Wave 0 has the ADSR 0x800000FF, the offset 0 with bit 31 set (in `BVAG`), 22050 Hz (0x5622), 2 blocks and
`extra` 0. Wave 1 has the ADSR 0x12345678, the offset 0 in `BPVG`, 11025 Hz (0x2B11), 1 block and `extra` 7. The
`TSEQ` slot of id 3 is 0x01000000: flags 1 and the record at offset 0. The record:

```text
00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F
4D 54 68 64 00 00 00 06 00 00 00 01 00 60
4D 54 72 6B 00 00 00 04 00 FF 2F 00
00 00
```

that is the header, `MThd` of 6 bytes (format 0, 1 track, 96 ticks per quarter note), `MTrk` of 4 bytes holding the
end-of-track event, and 2 zero bytes to reach 0x2C.

Exported, the folder holds `sdx.json`, `padding.bin` (the 0x5F0 zero bytes after the bank), `bank0/IA3P.bin`,
`bank0/TPAT.bin`, `bank0/IPAT.bin`, `bank0/waves/000.adpcm` (0x20 bytes), `bank0/waves/001.adpcm` (0x10 bytes) and
`bank0/sounds/0003.mid`. `sdx.json`, shown here with each wave and sound effect on one line:

```json
{
  "banks": [
    {
      "slot": 2,
      "waves": [
        {"sample_rate": 22050, "resident": true, "adsr": 2147483903, "extra": 0},
        {"sample_rate": 11025, "resident": false, "adsr": 305419896, "extra": 7}
      ],
      "sounds": [
        {"id": 3, "flags": 1, "header": "000102030405060708090a0b0c0d0e0f"}
      ]
    }
  ]
}
```
