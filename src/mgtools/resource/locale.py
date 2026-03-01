import json
from io import BufferedReader, BytesIO
from pathlib import Path

from translate.storage import po, xliff, xliff2
from translate.storage.xliff import ID_SEPARATOR

from mgtools.constants import (
    EXPORT_LOCALE_CHAR_SUBSTITUTION_MAP_FILENAME,
    EXPORT_LOCALE_RAW_FOLDER,
)
from mgtools.dataclasses.locale_format import LocaleFormat
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

            if isinstance(block_data, list):
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
        self.__blocks: dict[int, bytes | list[str]] = {}

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
        data_type: DataType | None = None,
    ) -> "Locale":
        if data_type is None:
            data_type = DataType(int.from_bytes(reader.read(2)))

            if data_type != DataType.MG1_SECTION:
                raise ValueError("Locale files must have MG1_SECTION data type.")

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

        text_groups = []
        if (file_path / "locale.xliff").exists():
            storage = xliff.Xliff1File().parsefile(str(file_path / "locale.xliff"))
            file_format = LocaleFormat.XLIFF
            text_groups = storage.getfilenames()
        elif (file_path / "locale.xlf").exists():
            storage = xliff2.Xliff2File().parsefile(str(file_path / "locale.xlf"))
            file_format = LocaleFormat.XLF
            text_groups = storage.getfilenames()
        else:
            file_format = LocaleFormat.PO

        idx = 0
        while (
            (file_path / f"{idx:02d}.po").exists() or f"block_{idx:02d}" in text_groups
        ) or (file_path / EXPORT_LOCALE_RAW_FOLDER / f"{idx:02d}.bin").exists():
            po_path = file_path / f"{idx:02d}.po"
            bin_path = file_path / EXPORT_LOCALE_RAW_FOLDER / f"{idx:02d}.bin"

            if file_format == LocaleFormat.PO and po_path.exists():
                storage = po.pofile().parsefile(str(po_path))

                block_stream = BytesIO()

                for unit in storage.units:
                    if unit.isheader():
                        continue

                    if not mg2:
                        block_stream.write((0).to_bytes(1))

                    string_unicode = unit.target or unit.source

                    string_data = write_mgscii_string(
                        string_unicode, char_substitution_map
                    )
                    string_length = len(string_data)

                    block_stream.write(string_length.to_bytes(2))
                    block_stream.write(string_data)

                block_data = block_stream.getvalue()
            elif (
                file_format in (LocaleFormat.XLIFF, LocaleFormat.XLF)
                and f"block_{idx:02d}" in text_groups
            ):
                units = storage.units  # type: ignore

                block_stream = BytesIO()

                if file_format == LocaleFormat.XLIFF:
                    for unit in units:
                        if unit.isheader():
                            continue

                        if unit.getid().split(ID_SEPARATOR, 1)[0] != f"block_{idx:02d}":
                            continue

                        if not mg2:
                            block_stream.write((0).to_bytes(1))

                        string_unicode = unit.target or unit.source

                        string_data = write_mgscii_string(
                            string_unicode, char_substitution_map
                        )
                        string_length = len(string_data)

                        block_stream.write(string_length.to_bytes(2))
                        block_stream.write(string_data)
                elif file_format == LocaleFormat.XLF:
                    for unit in units:
                        if unit.isheader():
                            continue

                        if unit.getid().split(":", 1)[0] != f"block_{idx:02d}":
                            continue

                        if not mg2:
                            block_stream.write((0).to_bytes(1))

                        string_unicode = unit.target or unit.source

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
            DataType.MG1_SECTION.value.to_bytes(2)
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

    def __parse_text_block(self, block_data: bytes, mg2: bool = False) -> list[str]:
        block_stream = BytesIO(block_data)
        parsed_block = []

        while block_stream.tell() < len(block_data):
            if mg2:
                raw_len = block_stream.read(2)
                if len(raw_len) < 2:
                    break
                string_length = int.from_bytes(raw_len)
            else:
                raw_flag = block_stream.read(1)
                if len(raw_flag) < 1:
                    break
                string_length = int.from_bytes(block_stream.read(2))

            if string_length == 0:
                break

            string_data = read_mgscii_string(block_stream.read(string_length))
            parsed_block.append(string_data)

        return parsed_block

    def __build_text_block(self, data: list[str], mg2: bool = False) -> bytes:
        block_stream = BytesIO()

        for entry in data:
            if not mg2:
                block_stream.write((0).to_bytes(1))

            string_data = write_mgscii_string(entry)
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

        locale_format = kwargs.get("locale_format")

        if locale_format is None:
            raise ValueError("Missing 'locale_format' in export kwargs.")

        match locale_format:
            case LocaleFormat.XLIFF:
                storage = xliff.Xliff1File()
                unit_class = xliff.Xliff1Unit
            case LocaleFormat.XLF:
                storage = xliff2.Xliff2File()
                unit_class = xliff2.Xliff2Unit

                root = storage.document.getroot()

                for child in root.getchildren():
                    if child.get("id") == "f1":
                        root.remove(child)
            case LocaleFormat.PO:
                storage = po.pofile()
                unit_class = po.pounit
            case _:
                raise ValueError(f"Unsupported locale format: {locale_format}")

        for block_idx, block_data in self.__blocks.items():
            if isinstance(block_data, list):
                if locale_format == LocaleFormat.XLIFF:
                    storage.switchfile(f"block_{block_idx:02d}", createifmissing=True)  # type: ignore
                    current_container = storage
                elif locale_format == LocaleFormat.XLF:
                    new_file_node = storage.createfilenode(f"block_{block_idx:02d}")  # type: ignore
                    storage.document.getroot().append(new_file_node)  # type: ignore
                    current_container = new_file_node
                else:
                    storage = po.pofile()  # type: ignore
                    current_container = storage

                for source_text in block_data:
                    unit = unit_class(source=source_text)

                    if locale_format == LocaleFormat.XLF:
                        current_container.append(unit.xmlelement)  # type: ignore
                    else:
                        current_container.addunit(unit)  # type: ignore

                if locale_format not in (LocaleFormat.XLIFF, LocaleFormat.XLF):
                    storage.savefile(
                        str(
                            output_path
                            / f"{block_idx:02d}.{locale_format.name.lower()}"
                        )
                    )
            elif isinstance(block_data, bytes):
                scripts_dir.mkdir(parents=True, exist_ok=True)
                with open(scripts_dir / f"{block_idx:02d}.bin", "wb") as f:
                    f.write(block_data)

        if locale_format in (LocaleFormat.XLIFF, LocaleFormat.XLF):
            storage.savefile(str(output_path / f"locale.{locale_format.name.lower()}"))
