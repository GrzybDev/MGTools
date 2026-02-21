import json
from io import BufferedReader, BytesIO
from pathlib import Path

import polib

from mgtools.constants import (
    EXPORT_LOCALE_CHAR_SUBSTITUTION_MAP_FILENAME,
    EXPORT_LOCALE_RAW_FOLDER,
)
from mgtools.enumerators.data_type import DataType
from mgtools.file import File
from mgtools.mgscii import read_mgscii_string, write_mgscii_string


class Locale(File):
    @property
    def raw_data(self) -> bytes:
        mg2 = self.data_type == DataType.MG2_SECTION
        file_bytes = b""

        for block_idx in sorted(self.__blocks.keys()):
            block_data = self.__blocks[block_idx]

            if isinstance(block_data, polib.POFile):
                block_bytes = self.__build_text_block(block_data, mg2=mg2)
            elif isinstance(block_data, bytes):
                block_bytes = block_data
            else:
                raise ValueError(f"Invalid block data type for block {block_idx}.")

            file_bytes += len(block_bytes).to_bytes(4) + block_bytes

        if mg2:
            return file_bytes

        return (
            self.data_type.value.to_bytes(2) + len(file_bytes).to_bytes(2) + file_bytes
        )

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__blocks: dict[int, bytes | polib.POFile] = {}

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
        data_type: DataType | None = None,
    ) -> "Locale":
        if data_type is None:
            data_type = DataType(int.from_bytes(reader.read(2)))

            if data_type != DataType.SIMPLE:
                raise ValueError("Locale files must have SIMPLE data type.")

            data_length = int.from_bytes(reader.read(2))
            data = BytesIO(reader.read(data_length))
        else:
            data = reader if isinstance(reader, BytesIO) else BytesIO(reader.read())

        f = Locale(data_type=data_type)

        index = 0
        while True:
            raw_size = data.read(4)
            if len(raw_size) < 4:
                break

            block_size = int.from_bytes(raw_size)

            if block_size == 0:
                break

            f.add_data(block_data=data.read(block_size), index=index)
            index += 1

        return f

    @staticmethod
    def from_file(
        file_path: Path,
        data_type: DataType | None = None,
    ) -> File:
        mg2 = data_type == DataType.MG2_SECTION
        locale_bytes = b""

        # Load char substitution map if exists
        char_substitution_map_path = (
            file_path.parent / EXPORT_LOCALE_CHAR_SUBSTITUTION_MAP_FILENAME
        )

        char_substitution_map = {}

        if char_substitution_map_path.exists():
            with open(char_substitution_map_path, "r", encoding="utf-8") as f:
                char_substitution_map = json.load(f)

        idx = 0
        while (file_path / f"{idx:02d}.po").exists() or (
            file_path / EXPORT_LOCALE_RAW_FOLDER / f"{idx:02d}.bin"
        ).exists():
            po_path = file_path / f"{idx:02d}.po"
            bin_path = file_path / EXPORT_LOCALE_RAW_FOLDER / f"{idx:02d}.bin"

            if po_path.exists():
                po = polib.pofile(str(po_path))

                block_stream = BytesIO()

                for entry in po:
                    if not mg2:
                        string_flag = int(entry.flags[0]) if entry.flags else 0
                        block_stream.write(string_flag.to_bytes(1))

                    string_unicode = entry.msgstr or entry.msgid

                    string_data = write_mgscii_string(
                        string_unicode, char_substitution_map
                    )
                    string_length = len(string_data)

                    block_stream.write(string_length.to_bytes(2))
                    block_stream.write(string_data)

                block_data = block_stream.getvalue()
            elif bin_path.exists():
                with open(bin_path, "rb") as block_file:
                    block_data = block_file.read()
            else:
                idx += 1
                continue

            locale_bytes += len(block_data).to_bytes(4) + block_data
            idx += 1

        if mg2:
            return Locale.from_stream(
                BytesIO(locale_bytes), data_type=DataType.MG2_SECTION
            )

        chunk_data = BytesIO(
            DataType.SIMPLE.value.to_bytes(2)
            + len(locale_bytes).to_bytes(2)
            + locale_bytes
        )

        return Locale.from_stream(chunk_data)

    @staticmethod
    def __is_text_block(block_data: bytes, mg2: bool = False) -> bool:
        stream = BytesIO(block_data)

        while stream.tell() < len(block_data):
            if mg2:
                raw_len = stream.read(2)
                if len(raw_len) < 2:
                    return False
                string_length = int.from_bytes(raw_len)
            else:
                raw_flag = stream.read(1)
                if len(raw_flag) < 1:
                    return False
                raw_len = stream.read(2)
                if len(raw_len) < 2:
                    return False
                string_length = int.from_bytes(raw_len)

            if string_length == 0:
                break

            if stream.tell() + string_length > len(block_data):
                return False

            stream.read(string_length)

        return stream.tell() == len(block_data)

    def __parse_text_block(self, block_data: bytes, mg2: bool = False) -> polib.POFile:
        po = polib.POFile()
        block_stream = BytesIO(block_data)

        while block_stream.tell() < len(block_data):
            if mg2:
                raw_len = block_stream.read(2)
                if len(raw_len) < 2:
                    break
                string_length = int.from_bytes(raw_len)
                string_flag = 0
            else:
                raw_flag = block_stream.read(1)
                if len(raw_flag) < 1:
                    break
                string_flag = int.from_bytes(raw_flag)
                string_length = int.from_bytes(block_stream.read(2))

            if string_length == 0:
                break

            string_data = read_mgscii_string(block_stream.read(string_length))

            po.append(
                polib.POEntry(
                    msgid=string_data,
                    msgstr="",
                    flags=[str(string_flag)] if not mg2 else [],
                )
            )

        return po

    def __build_text_block(self, po: polib.POFile, mg2: bool = False) -> bytes:
        block_stream = BytesIO()

        for entry in po:
            if not mg2:
                string_flag = int(entry.flags[0]) if entry.flags else 0
                block_stream.write(string_flag.to_bytes(1))

            string_data = write_mgscii_string(entry.msgstr or entry.msgid)
            string_length = len(string_data)

            block_stream.write(string_length.to_bytes(2))
            block_stream.write(string_data)

        return block_stream.getvalue()

    def add_data(self, **kwargs) -> None:
        if "block_data" not in kwargs:
            raise ValueError("Missing 'block_data' argument.")

        index = kwargs.get("index", len(self.__blocks))
        mg2 = self.data_type == DataType.MG2_SECTION
        raw = kwargs["block_data"]

        if self.__is_text_block(raw, mg2=mg2):
            self.__blocks[index] = self.__parse_text_block(raw, mg2=mg2)
        else:
            self.__blocks[index] = raw

    def export(self, output_path: Path, **kwargs) -> None:
        output_path.mkdir(parents=True, exist_ok=True)

        scripts_dir = output_path / EXPORT_LOCALE_RAW_FOLDER

        for block_idx, block_data in self.__blocks.items():
            if isinstance(block_data, polib.POFile):
                block_data.save(str(output_path / f"{block_idx:02d}.po"))
            elif isinstance(block_data, bytes):
                scripts_dir.mkdir(parents=True, exist_ok=True)
                with open(scripts_dir / f"{block_idx:02d}.bin", "wb") as f:
                    f.write(block_data)
