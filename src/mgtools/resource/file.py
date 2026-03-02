import json
from io import BytesIO
from pathlib import Path

from mgtools.constants import (
    EXPORT_FONT_FOLDER,
    EXPORT_LOCALE_FOLDER,
    EXPORT_PALETTE_EXTENSION,
    EXPORT_SPRITE_EXTENSION,
    EXPORT_SPRITE_FOLDER,
    EXPORT_TEXTURE_EXTENSION,
    EXPORT_TEXTURE_FOLDER,
    EXPORT_UNKNOWN_EXTENSION,
    EXPORT_UNKNOWN_FOLDER,
    RESOURCE_MARKER,
    RESOURCE_METADATA_FILENAME,
)
from mgtools.enumerators.data_type import DataType
from mgtools.enumerators.file_type import FileType
from mgtools.enumerators.game import Game
from mgtools.mg1.constants import (
    RESOURCE_IDENTIFIER as MG1_RESOURCE_IDENTIFIER,
)
from mgtools.mg1.constants import (
    RESOURCE_SECTION_COUNT,
)
from mgtools.mg1.mappings import (
    DATA_TYPE_MAP as MG1_DATA_TYPE_MAP,
)
from mgtools.mg1.mappings import (
    FILE_TYPE_MAP as MG1_FILE_TYPE_MAP,
)
from mgtools.mg2.mappings import (
    DATA_TYPE_MAP as MG2_DATA_TYPE_MAP,
)
from mgtools.mg2.mappings import (
    FILE_TYPE_MAP as MG2_FILE_TYPE_MAP,
)
from mgtools.resource.asset import Asset
from mgtools.resource.assets.font import Font
from mgtools.resource.assets.locale import Locale
from mgtools.resource.assets.palette import Palette
from mgtools.resource.assets.sprite import Sprite
from mgtools.resource.assets.sprite_framed import FramedSprite
from mgtools.resource.assets.texture import Texture
from mgtools.resource.assets.unknown import UnknownFile

_FILE_CLASSES: dict[FileType, type[Asset]] = {
    FileType.SPRITE: Sprite,
    FileType.PALETTE: Palette,
    FileType.LOCALE: Locale,
    FileType.FONT: Font,
    FileType.SPRITE_FRAMED: FramedSprite,
    FileType.TEXTURE: Texture,
}

_EXPORT_LAYOUT: dict[FileType, tuple[str, str]] = {
    FileType.SPRITE: (EXPORT_SPRITE_EXTENSION, EXPORT_SPRITE_FOLDER),
    FileType.PALETTE: (EXPORT_PALETTE_EXTENSION, ""),
    FileType.LOCALE: ("", EXPORT_LOCALE_FOLDER),
    FileType.FONT: ("", EXPORT_FONT_FOLDER),
    FileType.SPRITE_FRAMED: (EXPORT_SPRITE_EXTENSION, EXPORT_SPRITE_FOLDER),
    FileType.TEXTURE: (EXPORT_TEXTURE_EXTENSION, EXPORT_TEXTURE_FOLDER),
}


class Resource:
    __game: Game

    @property
    def section_count(self) -> int:
        return len(self.__sections)

    def __init__(self, game: Game, header_bytes: bytes = b"\x00\x00") -> None:
        self.__game = game
        self.__header_bytes = header_bytes
        self.__sections: list[Asset] = []

    def __str__(self) -> str:
        return f"Resource(game={self.__game.name}, section_count={self.section_count})"

    def save_metadata(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = output_dir / RESOURCE_METADATA_FILENAME

        metadata: dict = {"game": self.__game.value}

        if self.__game == Game.MG1 and self.__header_bytes != b"\x00\x00":
            metadata["header_bytes"] = self.__header_bytes.hex()

        # Save per-section identifiers for types that have them (MG1 only)
        section_identifiers: dict[str, str] = {}

        if self.__game == Game.MG1:
            file_type_map = self.__get_file_type_map()

            for idx, section in enumerate(self.__sections):
                file_type = file_type_map.get(idx, FileType.UNKNOWN)
                if file_type in (FileType.FONT, FileType.TEXTURE):
                    # Identifier is bytes [2:4] of raw_data (after data_type)
                    raw = section.raw_data
                    identifier = raw[2:4]
                    if identifier != b"\x00\x00":
                        section_identifiers[str(idx)] = identifier.hex()

        if section_identifiers:
            metadata["section_identifiers"] = section_identifiers

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    @staticmethod
    def detect_game(input_dir: Path) -> Game:
        metadata_path = input_dir / RESOURCE_METADATA_FILENAME

        if not metadata_path.is_file():
            raise FileNotFoundError(
                f"Metadata file not found: {metadata_path}\n"
                "This folder was not created by 'mgtools export' or the "
                f"'{RESOURCE_METADATA_FILENAME}' file was deleted."
            )

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        game_value = metadata.get("game")

        try:
            return Game(game_value)
        except ValueError:
            raise ValueError(f"Unknown game '{game_value}' in {metadata_path}")

    @staticmethod
    def load_metadata(input_dir: Path) -> dict:
        """Load resource metadata including game and optional header_bytes."""
        metadata_path = input_dir / RESOURCE_METADATA_FILENAME

        if not metadata_path.is_file():
            raise FileNotFoundError(
                f"Metadata file not found: {metadata_path}\n"
                "This folder was not created by 'mgtools export' or the "
                f"'{RESOURCE_METADATA_FILENAME}' file was deleted."
            )

        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def from_file(file_path: Path) -> "Resource":
        file_size = file_path.stat().st_size

        with open(file_path, "rb") as f:
            marker = f.read(1)[0]

            if marker != RESOURCE_MARKER:
                raise ValueError(f"Invalid resource marker: 0x{marker:02x}")

            identifier = f.read(1)[0]

            if identifier == MG1_RESOURCE_IDENTIFIER:
                # MG1 format: marker + identifier + 2-byte header + sections
                header_bytes = f.read(2)

                res = Resource(Game.MG1, header_bytes=header_bytes)

                for idx in range(RESOURCE_SECTION_COUNT):
                    res.__read_mg1_section(idx, f)
            else:
                # MG2 format: marker + 3-byte content size + sections
                content_size = (identifier << 16) | int.from_bytes(f.read(2), "big")

                if content_size != file_size - 4:
                    raise ValueError(
                        "Invalid MG2 resource file: content size mismatch."
                    )

                res = Resource(Game.MG2)

                while f.tell() < file_size:
                    section_idx = len(res.__sections)
                    res.__read_mg2_section(section_idx, f)

        return res

    def __read_mg1_section(self, index, reader) -> None:
        if self.__game != Game.MG1:
            raise ValueError(f"Attempted to read MG1 section for game {self.__game}")

        file_type = MG1_FILE_TYPE_MAP.get(index, FileType.UNKNOWN)
        cls = _FILE_CLASSES.get(file_type, UnknownFile)
        self.__sections.append(cls.from_stream(reader))

    def __read_mg2_section(self, index, reader) -> None:
        if self.__game != Game.MG2:
            raise ValueError(f"Attempted to read MG2 section for game {self.__game}")

        section_marker = reader.read(1)

        if section_marker[0] != RESOURCE_MARKER:
            raise ValueError(
                f"Invalid MG2 section marker at index {index}: "
                f"0x{section_marker[0]:02x}"
            )

        section_size = int.from_bytes(reader.read(3), "big")
        section_data = reader.read(section_size)

        file_type = MG2_FILE_TYPE_MAP.get(index, FileType.UNKNOWN)
        cls = _FILE_CLASSES.get(file_type, UnknownFile)
        self.__sections.append(
            cls.from_stream(BytesIO(section_data), data_type=DataType.MG2_SECTION)
        )

    def unpack(self, output_dir: Path, section_index: int, **kwargs) -> None:
        file = self.__sections[section_index]
        file_type_map = self.__get_file_type_map()

        # Apply palette to sprites if a palette section exists
        if isinstance(file, (Sprite, FramedSprite)):
            for section in self.__sections:
                if isinstance(section, Palette):
                    file.add_palette(section)
                    break

        file_type = file_type_map.get(section_index, FileType.UNKNOWN)
        export_name = f"{section_index:02d}"

        if file_type in _EXPORT_LAYOUT:
            ext, folder = _EXPORT_LAYOUT[file_type]
            export_name = f"{export_name}.{ext}" if ext else ""
            export_dir = output_dir / folder if folder else output_dir
        else:
            export_name = f"{export_name}.{EXPORT_UNKNOWN_EXTENSION}"
            export_dir = output_dir / EXPORT_UNKNOWN_FOLDER

        export_dir.mkdir(parents=True, exist_ok=True)
        file.export(export_dir / export_name, **kwargs)

    def __get_file_type_map(self) -> dict:
        if self.__game == Game.MG1:
            return MG1_FILE_TYPE_MAP
        if self.__game == Game.MG2:
            return MG2_FILE_TYPE_MAP
        raise ValueError(f"Unsupported game: {self.__game}")

    def add_from_folder(self, input_dir: Path, section_index: int, **kwargs) -> None:
        if self.__game == Game.MG1:
            default_data_type = DataType.MG1_SECTION
            data_type_map = MG1_DATA_TYPE_MAP
        elif self.__game == Game.MG2:
            default_data_type = DataType.MG2_SECTION
            data_type_map = MG2_DATA_TYPE_MAP
        else:
            raise ValueError(f"Unsupported game: {self.__game}")

        file_type_map = self.__get_file_type_map()
        file_type = file_type_map.get(section_index, FileType.UNKNOWN)
        section_name = f"{section_index:02d}"

        # Look up per-section identifier from metadata
        section_identifiers = kwargs.get("section_identifiers", {})
        identifier_hex = section_identifiers.get(str(section_index))
        identifier = bytes.fromhex(identifier_hex) if identifier_hex else b"\0\0"

        if file_type in _EXPORT_LAYOUT:
            ext, folder = _EXPORT_LAYOUT[file_type]
            source_dir = input_dir / folder if folder else input_dir
            source_path = source_dir / f"{section_name}.{ext}" if ext else source_dir

            data_type = DataType.MG2_SECTION if self.__game == Game.MG2 else None

            cls = _FILE_CLASSES[file_type]
            extra_kwargs: dict = {}
            if file_type in (FileType.FONT, FileType.TEXTURE):
                extra_kwargs["identifier"] = identifier
            self.__sections.append(
                cls.from_file(source_path, data_type=data_type, **extra_kwargs)
            )
        else:
            source_name = f"{section_name}.{EXPORT_UNKNOWN_EXTENSION}"
            source_dir = input_dir / EXPORT_UNKNOWN_FOLDER
            data_type = data_type_map.get(section_index, default_data_type)

            self.__sections.append(
                UnknownFile.from_file(source_dir / source_name, data_type=data_type)
            )

    def save(self, output_path: Path) -> None:
        with open(output_path, "wb") as f:
            if self.__game == Game.MG1:
                f.write(bytes([RESOURCE_MARKER, MG1_RESOURCE_IDENTIFIER]))
                f.write(self.__header_bytes)

                for file in self.__sections:
                    f.write(file.raw_data)
            elif self.__game == Game.MG2:
                # Collect all section data
                content = b""

                for file in self.__sections:
                    section_data = file.raw_data
                    content += (
                        bytes([RESOURCE_MARKER])
                        + len(section_data).to_bytes(3, "big")
                        + section_data
                    )

                # Write outer wrapper: marker + 3-byte content size
                f.write(
                    bytes([RESOURCE_MARKER]) + len(content).to_bytes(3, "big") + content
                )
            else:
                raise ValueError(f"Unsupported game: {self.__game}")
