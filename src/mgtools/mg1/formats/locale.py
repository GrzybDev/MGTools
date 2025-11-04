import os
from io import BytesIO
from pathlib import Path

import polib

from mgtools.file import File
from mgtools.mg1.chunks.single import Single
from mgtools.mg1.constants import EXPORT_LOCALE_EXTENSION
from mgtools.mg1.mappings import TEXT_BLOCKS, TEXT_BLOCKS_NAMES


class Locale(File):

    def __init__(self, chunk: Single) -> None:
        self.__block_data = []
        self.__locale_data = {}

        self.__parse_data(chunk.data)

    def __parse_data(self, chunk: BytesIO) -> None:
        while True:
            block_size = int.from_bytes(chunk.read(4))

            if block_size == 0:
                break

            self.__block_data.append(chunk.read(block_size))

        for block_id in TEXT_BLOCKS:
            block_bytes = BytesIO(self.__block_data[block_id])
            strings = []

            while True:
                block_bytes.seek(1, os.SEEK_CUR)
                string_length = int.from_bytes(block_bytes.read(2))

                if string_length == 0:
                    break

                string_data = block_bytes.read(string_length)
                strings.append(string_data.decode("shift_jis"))

            self.__locale_data[block_id] = strings

    def save(self, path: Path) -> None:
        for block_id, strings in self.__locale_data.items():
            po = polib.POFile()

            for string in strings:
                entry = polib.POEntry(msgid=string, msgstr="")
                po.append(entry)

            block_name = TEXT_BLOCKS_NAMES.get(block_id, f"{block_id}")
            po.save(str(path / f"{block_name}.{EXPORT_LOCALE_EXTENSION}"))
