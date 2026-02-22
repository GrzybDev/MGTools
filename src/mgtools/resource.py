import json
from io import BytesIO
from pathlib import Path

from mgtools.constants import (
    EXPORT_FONT_FOLDER,
    EXPORT_LOCALE_FOLDER,
    EXPORT_PALETTE_EXTENSION,
    EXPORT_SPRITE_EXTENSION,
    EXPORT_SPRITE_FOLDER,
    EXPORT_UNKNOWN_EXTENSION,
    EXPORT_UNKNOWN_FOLDER,
    RESOURCE_MARKER,
    RESOURCE_METADATA_FILENAME,
)
from mgtools.enumerators.data_type import DataType
from mgtools.enumerators.file_type import FileType
from mgtools.enumerators.game import Game
from mgtools.file import File
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
from mgtools.readers.font import Font
from mgtools.readers.locale import Locale
from mgtools.readers.palette import Palette
from mgtools.readers.sprite import Sprite
from mgtools.readers.sprite_framed import FramedSprite
from mgtools.readers.unknown import UnknownFile


class Resource:
    __game: Game

    @property
    def section_count(self) -> int:
        return len(self.__sections)

    def __init__(self, game: Game, header_bytes: bytes = b"\x00\x00") -> None:
        self.__game = game
        self.__header_bytes = header_bytes
        self.__sections: list[File] = []

    def __str__(self) -> str:
        return f"Resource(game={self.__game.name}, section_count={self.section_count})"

    def save_metadata(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = output_dir / RESOURCE_METADATA_FILENAME

        metadata = {"game": self.__game.value}

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

        match MG1_FILE_TYPE_MAP.get(index, FileType.UNKNOWN):
            case FileType.SPRITE:
                sprite = Sprite.from_stream(reader)
                self.__sections.append(sprite)
            case FileType.PALETTE:
                palette = Palette.from_stream(reader)
                self.__sections.append(palette)
            case FileType.LOCALE:
                locale = Locale.from_stream(reader)
                self.__sections.append(locale)
            case FileType.FONT:
                font = Font.from_stream(reader)
                self.__sections.append(font)
            case FileType.SPRITE_FRAMED:
                framed_sprite = FramedSprite.from_stream(reader)
                self.__sections.append(framed_sprite)
            case _:
                file = UnknownFile.from_stream(reader)
                self.__sections.append(file)

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

        match file_type:
            case FileType.LOCALE:
                locale = Locale.from_stream(
                    BytesIO(section_data), data_type=DataType.MG2_SECTION
                )
                self.__sections.append(locale)
            case _:
                file = UnknownFile.from_stream(
                    BytesIO(section_data), data_type=DataType.MG2_SECTION
                )
                self.__sections.append(file)

    def export(self, output_dir: Path, section_index: int, **kwargs) -> None:
        file = self.__sections[section_index]

        if self.__game == Game.MG1:
            file_type_map = MG1_FILE_TYPE_MAP
        elif self.__game == Game.MG2:
            file_type_map = MG2_FILE_TYPE_MAP
        else:
            raise ValueError(f"Unsupported game: {self.__game}")

        # Apply palette to sprites and tiles if a palette section exists
        for section in self.__sections:
            if (isinstance(file, (Sprite, FramedSprite))) and isinstance(
                section, Palette
            ):
                file.add_palette(section)
                break

        export_name = f"{section_index:02d}"

        match file_type_map.get(section_index, FileType.UNKNOWN):
            case FileType.SPRITE:
                export_name = f"{export_name}.{EXPORT_SPRITE_EXTENSION}"
                export_dir = output_dir / EXPORT_SPRITE_FOLDER
            case FileType.PALETTE:
                export_name = f"{export_name}.{EXPORT_PALETTE_EXTENSION}"
                export_dir = output_dir
            case FileType.LOCALE:
                export_name = ""
                export_dir = output_dir / EXPORT_LOCALE_FOLDER
            case FileType.FONT:
                export_name = ""
                export_dir = output_dir / EXPORT_FONT_FOLDER
            case FileType.SPRITE_FRAMED:
                export_name = f"{export_name}.{EXPORT_SPRITE_EXTENSION}"
                export_dir = output_dir / EXPORT_SPRITE_FOLDER
            case _:
                export_name = f"{export_name}.{EXPORT_UNKNOWN_EXTENSION}"
                export_dir = output_dir / EXPORT_UNKNOWN_FOLDER

        export_dir.mkdir(parents=True, exist_ok=True)
        file.export(export_dir / export_name, **kwargs)

    def add_from_folder(self, input_dir: Path, section_index: int) -> None:
        if self.__game == Game.MG1:
            default_data_type = DataType.MG1_SECTION
            data_type_map = MG1_DATA_TYPE_MAP
            file_type_map = MG1_FILE_TYPE_MAP
        elif self.__game == Game.MG2:
            default_data_type = DataType.MG2_SECTION
            data_type_map = MG2_DATA_TYPE_MAP
            file_type_map = MG2_FILE_TYPE_MAP
        else:
            raise ValueError(f"Unsupported game: {self.__game}")

        section_name = f"{section_index:02d}"

        match file_type_map.get(section_index, FileType.UNKNOWN):
            case FileType.SPRITE:
                source_name = f"{section_name}.{EXPORT_SPRITE_EXTENSION}"
                source_dir = input_dir / EXPORT_SPRITE_FOLDER

                file = Sprite.from_file(source_dir / source_name)
                self.__sections.append(file)
            case FileType.PALETTE:
                source_name = f"{section_name}.{EXPORT_PALETTE_EXTENSION}"
                source_dir = input_dir

                file = Palette.from_file(source_dir / source_name)
                self.__sections.append(file)
            case FileType.LOCALE:
                source_dir = input_dir / EXPORT_LOCALE_FOLDER

                if self.__game == Game.MG2:
                    file = Locale.from_file(source_dir, data_type=DataType.MG2_SECTION)
                else:
                    file = Locale.from_file(source_dir)
                self.__sections.append(file)
            case FileType.FONT:
                source_dir = input_dir / EXPORT_FONT_FOLDER

                file = Font.from_file(source_dir)
                self.__sections.append(file)
            case FileType.SPRITE_FRAMED:
                source_name = f"{section_name}.{EXPORT_SPRITE_EXTENSION}"
                source_dir = input_dir / EXPORT_SPRITE_FOLDER

                file = FramedSprite.from_file(source_dir / source_name)
                self.__sections.append(file)
            case _:
                source_name = f"{section_name}.{EXPORT_UNKNOWN_EXTENSION}"
                source_dir = input_dir / EXPORT_UNKNOWN_FOLDER
                data_type = data_type_map.get(section_index, default_data_type)

                file = UnknownFile.from_file(
                    source_dir / source_name, data_type=data_type
                )
                self.__sections.append(file)

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
