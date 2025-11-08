from io import BufferedReader, BytesIO
from pathlib import Path

import polib

from mgtools.constants import EXPORT_LOCALE_SCRIPTS_FOLDER
from mgtools.enumerators.data_type import DataType
from mgtools.file import File
from mgtools.mg1.constants import LOCALE_BLOCKS_COUNT
from mgtools.mg1.mappings import TEXT_BLOCKS


class Locale(File):

    @property
    def raw_data(self) -> bytes:
        file_bytes = b""

        for block_idx, block_data in self.__blocks.items():
            if block_idx in TEXT_BLOCKS and isinstance(block_data, polib.POFile):
                block_bytes = self.__build_text_block(block_data)
            elif isinstance(block_data, bytes):
                block_bytes = block_data
            else:
                raise ValueError(f"Invalid block data type for block {block_idx}.")

            file_bytes += len(block_bytes).to_bytes(4) + block_bytes

        return (
            self.data_type.value.to_bytes(2) + len(file_bytes).to_bytes(2) + file_bytes
        )

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__blocks: dict[int, bytes | polib.POFile] = {}

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
    ) -> Locale:
        data_type = DataType(int.from_bytes(reader.read(2)))

        if data_type != DataType.SIMPLE:
            raise ValueError("Locale files must have SIMPLE data type.")

        data_length = int.from_bytes(reader.read(2))
        data = BytesIO(reader.read(data_length))

        f = Locale(data_type=data_type)

        index = 0
        while True:
            block_size = int.from_bytes(data.read(4))

            if block_size == 0:
                break

            f.add_data(block_data=data.read(block_size), index=index)
            index += 1

        return f

    @staticmethod
    def from_file(file_path: Path) -> File:
        locale_bytes = b""

        for idx in range(LOCALE_BLOCKS_COUNT):
            if idx not in TEXT_BLOCKS:
                block_path = file_path / EXPORT_LOCALE_SCRIPTS_FOLDER / f"{idx:02d}.bin"

                with open(block_path, "rb") as block_file:
                    block_data = block_file.read()

                locale_bytes += len(block_data).to_bytes(4) + block_data
            else:
                block_path = file_path / f"{idx:02d}.po"
                po = polib.pofile(str(block_path))

                block_stream = BytesIO()

                for entry in po:
                    string_flag = int(entry.flags[0]) if entry.flags else 0
                    string_data = (entry.msgstr or entry.msgid).encode("shift_jis")
                    string_length = len(string_data)

                    block_stream.write(string_flag.to_bytes(1))
                    block_stream.write(string_length.to_bytes(2))
                    block_stream.write(string_data)

                block_data = block_stream.getvalue()
                locale_bytes += len(block_data).to_bytes(4) + block_data

        chunk_data = BytesIO(
            DataType.SIMPLE.value.to_bytes(2)
            + len(locale_bytes).to_bytes(2)
            + locale_bytes
        )

        return Locale.from_stream(chunk_data)

    def __parse_text_block(self, block_data: bytes) -> polib.POFile:
        po = polib.POFile()
        block_stream = BytesIO(block_data)

        while True:
            string_flag = int.from_bytes(block_stream.read(1))
            string_length = int.from_bytes(block_stream.read(2))

            if string_length == 0:
                break

            string_data = block_stream.read(string_length).decode("shift_jis")
            po.append(
                polib.POEntry(
                    msgid=string_data,
                    msgstr="",
                    flags=[str(string_flag)],
                )
            )

        return po

    def __build_text_block(self, po: polib.POFile) -> bytes:
        block_stream = BytesIO()

        for entry in po:
            string_flag = int(entry.flags[0]) if entry.flags else 0
            string_data = (entry.msgstr or entry.msgid).encode("shift_jis")
            string_length = len(string_data)

            block_stream.write(string_flag.to_bytes(1))
            block_stream.write(string_length.to_bytes(2))
            block_stream.write(string_data)

        return block_stream.getvalue()

    def add_data(self, **kwargs) -> None:
        if "block_data" not in kwargs:
            raise ValueError("Missing 'block_data' argument.")

        index = kwargs.get("index", len(self.__blocks))

        if index in TEXT_BLOCKS:
            block_data = self.__parse_text_block(kwargs["block_data"])
        else:
            block_data = kwargs["block_data"]

        self.__blocks[index] = block_data

    def export(self, output_path: Path, **kwargs) -> None:
        scripts_dir = output_path / EXPORT_LOCALE_SCRIPTS_FOLDER
        scripts_dir.mkdir(parents=True, exist_ok=True)

        for block_idx, block_data in self.__blocks.items():
            if block_idx in TEXT_BLOCKS and isinstance(block_data, polib.POFile):
                block_data.save(str(output_path / f"{block_idx:02d}.po"))
            elif isinstance(block_data, bytes):
                with open(scripts_dir / f"{block_idx:02d}.bin", "wb") as f:
                    f.write(block_data)
