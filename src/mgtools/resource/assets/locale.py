import json
from io import BufferedReader, BytesIO
from pathlib import Path

from translate.storage import po, xliff, xliff2
from translate.storage.base import TranslationStore, TranslationUnit
from translate.storage.xliff import ID_SEPARATOR

from mgtools.constants import (
    EXPORT_LOCALE_CHAR_SUBSTITUTION_MAP_FILENAME,
    EXPORT_LOCALE_RAW_FOLDER,
)
from mgtools.dataclasses.locale_format import LocaleFormat
from mgtools.enumerators.data_type import DataType
from mgtools.resource.asset import Asset
from mgtools.utilities.mgscii import read_mgscii_string, write_mgscii_string

# ID separator used per locale format when filtering units by block name
_UNIT_ID_SEPARATORS = {
    LocaleFormat.XLIFF: ID_SEPARATOR,
    LocaleFormat.XLF: ":",
}


class Locale(Asset):
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

        return self.data_type.to_bytes(2) + len(file_bytes).to_bytes(2) + file_bytes

    def __init__(self, data_type: DataType) -> None:
        super().__init__(data_type)
        self.__blocks: dict[int, bytes | list[tuple[int, str]]] = {}

    @staticmethod
    def from_stream(
        reader: BufferedReader | BytesIO,
        data_type: DataType | None = None,
    ) -> Asset:
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
    ) -> Asset:
        mg2 = data_type == DataType.MG2_SECTION
        char_map = Locale.__load_char_substitution_map(file_path)
        file_format, storage, text_groups = Locale.__detect_format(file_path)

        locale_bytes = b""
        idx = 0

        while (
            (file_path / f"{idx:02d}.po").exists()
            or f"block_{idx:02d}" in text_groups
            or (file_path / EXPORT_LOCALE_RAW_FOLDER / f"{idx:02d}.bin").exists()
        ):
            block_data = Locale.__read_block(
                file_path, idx, file_format, storage, text_groups, mg2, char_map
            )

            if block_data is not None:
                locale_bytes += len(block_data).to_bytes(4) + block_data

            idx += 1

        if mg2:
            return Locale.from_stream(
                BytesIO(locale_bytes), data_type=DataType.MG2_SECTION
            )

        chunk_data = BytesIO(
            DataType.MG1_SECTION.to_bytes(2)
            + len(locale_bytes).to_bytes(2)
            + locale_bytes
        )

        return Locale.from_stream(chunk_data)

    @staticmethod
    def __load_char_substitution_map(file_path: Path) -> dict[str, int]:
        map_path = file_path.parent / EXPORT_LOCALE_CHAR_SUBSTITUTION_MAP_FILENAME

        if map_path.exists():
            with open(map_path, "r", encoding="utf-8") as f:
                raw: dict[str, int] = json.load(f)
                return raw

        return {}

    @staticmethod
    def __detect_format(
        file_path: Path,
    ) -> tuple[LocaleFormat, TranslationStore | None, list[str]]:
        """Return (format, storage_or_None, text_groups)."""
        if (file_path / "locale.xliff").exists():
            storage = xliff.Xliff1File().parsefile(str(file_path / "locale.xliff"))
            return LocaleFormat.XLIFF, storage, storage.getfilenames()

        if (file_path / "locale.xlf").exists():
            storage = xliff2.Xliff2File().parsefile(str(file_path / "locale.xlf"))
            return LocaleFormat.XLF, storage, storage.getfilenames()

        return LocaleFormat.PO, None, []

    @staticmethod
    def __read_block(
        file_path: Path,
        idx: int,
        file_format: LocaleFormat,
        storage: TranslationStore | None,
        text_groups: list[str],
        mg2: bool,
        char_map: dict[str, int],
    ) -> bytes | None:
        block_name = f"block_{idx:02d}"
        po_path = file_path / f"{idx:02d}.po"
        bin_path = file_path / EXPORT_LOCALE_RAW_FOLDER / f"{idx:02d}.bin"

        if file_format == LocaleFormat.PO and po_path.exists():
            po_storage = po.pofile().parsefile(str(po_path))
            units = [u for u in po_storage.units if not u.isheader()]
            return Locale.__units_to_block(units, mg2, char_map)

        if file_format in _UNIT_ID_SEPARATORS and block_name in text_groups:
            assert storage is not None
            separator = _UNIT_ID_SEPARATORS[file_format]
            units = [
                u
                for u in storage.units
                if not u.isheader() and u.getid().split(separator, 1)[0] == block_name
            ]
            return Locale.__units_to_block(units, mg2, char_map)

        if bin_path.exists():
            with open(bin_path, "rb") as f:
                return f.read()

        return None

    @staticmethod
    def __units_to_block(
        units: list[TranslationUnit], mg2: bool, char_map: dict[str, int]
    ) -> bytes:
        stream = BytesIO()

        for unit in units:
            prefix = Locale.__extract_prefix(unit)
            Locale.__write_string_entry(
                stream,
                str(unit.target or unit.source),
                mg2,
                char_map,
                prefix=prefix,
            )

        return stream.getvalue()

    @staticmethod
    def __extract_prefix(unit: TranslationUnit) -> int:
        """Read the MG1 entry prefix byte stored in a developer note."""
        notes = unit.getnotes(origin="developer")
        if notes:
            for line in notes.split("\n"):
                line = line.strip()
                if line.startswith("mg1_prefix:"):
                    try:
                        return int(line.split(":", 1)[1])
                    except (ValueError, IndexError):
                        pass
        return 0

    @staticmethod
    def __write_string_entry(
        stream: BytesIO,
        text: str,
        mg2: bool,
        char_map: dict[str, int] | None = None,
        prefix: int = 0,
    ) -> None:
        if not mg2:
            stream.write(prefix.to_bytes(1))

        string_data = write_mgscii_string(text, char_map or {})
        stream.write(len(string_data).to_bytes(2))
        stream.write(string_data)

    @staticmethod
    def __try_parse_text_block(
        block_data: bytes, mg2: bool = False
    ) -> list[tuple[int, str]] | None:
        """Parse block_data as a text block.

        Returns list of (prefix, decoded_string) tuples on success,
        None if the data does not look like a valid text block.
        """
        stream = BytesIO(block_data)
        result: list[tuple[int, str]] = []

        while stream.tell() < len(block_data):
            prefix = 0
            if not mg2:
                raw_prefix = stream.read(1)
                if len(raw_prefix) < 1:
                    return None
                prefix = raw_prefix[0]

            raw_len = stream.read(2)
            if len(raw_len) < 2:
                return None

            string_length = int.from_bytes(raw_len)

            if string_length == 0:
                break

            if stream.tell() + string_length > len(block_data):
                return None

            result.append((prefix, read_mgscii_string(stream.read(string_length))))

        if stream.tell() != len(block_data):
            return None

        return result

    def __build_text_block(
        self, data: list[tuple[int, str]], mg2: bool = False
    ) -> bytes:
        stream = BytesIO()

        for prefix, text in data:
            self.__write_string_entry(stream, text, mg2, prefix=prefix)

        return stream.getvalue()

    def add_data(self, **kwargs) -> None:
        if "block_data" not in kwargs:
            raise ValueError("Missing 'block_data' argument.")

        index = kwargs.get("index", len(self.__blocks))
        mg2 = self.data_type == DataType.MG2_SECTION
        raw = kwargs["block_data"]

        parsed = self.__try_parse_text_block(raw, mg2=mg2)
        self.__blocks[index] = parsed if parsed is not None else raw

    def export(self, output_path: Path, **kwargs) -> None:
        output_path.mkdir(parents=True, exist_ok=True)

        locale_format = kwargs.get("locale_format")

        if locale_format is None:
            raise ValueError("Missing 'locale_format' in export kwargs.")

        storage = self.__create_storage(locale_format)

        for block_idx, block_data in self.__blocks.items():
            if isinstance(block_data, list):
                self.__export_text_block(
                    output_path,
                    block_idx,
                    block_data,
                    locale_format,
                    storage,
                )
            elif isinstance(block_data, bytes):
                raw_dir = output_path / EXPORT_LOCALE_RAW_FOLDER
                raw_dir.mkdir(parents=True, exist_ok=True)

                with open(raw_dir / f"{block_idx:02d}.bin", "wb") as f:
                    f.write(block_data)

        if locale_format in (LocaleFormat.XLIFF, LocaleFormat.XLF):
            storage.savefile(str(output_path / f"locale.{locale_format.name.lower()}"))

    @staticmethod
    def __create_storage(
        locale_format: LocaleFormat,
    ) -> TranslationStore:
        match locale_format:
            case LocaleFormat.XLIFF:
                return xliff.Xliff1File()
            case LocaleFormat.XLF:
                storage = xliff2.Xliff2File()
                root = storage.document.getroot()

                for child in root.getchildren():
                    if child.get("id") == "f1":
                        root.remove(child)

                return storage
            case LocaleFormat.PO:
                return po.pofile()
            case _:
                raise ValueError(f"Unsupported locale format: {locale_format}")

    @staticmethod
    def __export_text_block(
        output_path: Path,
        block_idx: int,
        block_data: list[tuple[int, str]],
        locale_format: LocaleFormat,
        storage: TranslationStore,
    ) -> None:
        block_name = f"block_{block_idx:02d}"

        match locale_format:
            case LocaleFormat.XLIFF:
                assert isinstance(storage, xliff.Xliff1File)
                storage.switchfile(block_name, createifmissing=True)

                for prefix, source_text in block_data:
                    unit = xliff.Xliff1Unit(source=source_text)
                    if prefix != 0:
                        unit.addnote(f"mg1_prefix:{prefix}", origin="developer")
                    storage.addunit(unit)

            case LocaleFormat.XLF:
                assert isinstance(storage, xliff2.Xliff2File)
                file_node = storage.createfilenode(block_name)
                storage.document.getroot().append(file_node)

                for prefix, source_text in block_data:
                    unit = xliff2.Xliff2Unit(source=source_text)
                    if prefix != 0:
                        unit.addnote(f"mg1_prefix:{prefix}", origin="developer")
                    file_node.append(unit.xmlelement)

            case _:
                po_storage = po.pofile()

                for prefix, source_text in block_data:
                    unit = po.pounit(source=source_text)
                    if prefix != 0:
                        unit.addnote(f"mg1_prefix:{prefix}", origin="developer")
                    po_storage.addunit(unit)

                po_storage.savefile(
                    str(output_path / f"{block_idx:02d}.{locale_format.name.lower()}")
                )
