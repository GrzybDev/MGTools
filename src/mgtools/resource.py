from pathlib import Path

from mgtools.constants import (
    EXPORT_FONT_FOLDER,
    EXPORT_LOCALE_FOLDER,
    EXPORT_PALETTE_EXTENSION,
    EXPORT_SPRITE_EXTENSION,
    EXPORT_SPRITE_FOLDER,
    EXPORT_UNKNOWN_EXTENSION,
    EXPORT_UNKNOWN_FOLDER,
)
from mgtools.enumerators.data_type import DataType
from mgtools.enumerators.file_type import FileType
from mgtools.enumerators.game import Game
from mgtools.enumerators.platform import Platform
from mgtools.file import File
from mgtools.mg1.constants import RESOURCE_FILES_COUNT, RESOURCE_MAGIC
from mgtools.mg1.mappings import DATA_TYPE_MAP, FILE_NAME_MAP, FILE_TYPE_MAP
from mgtools.readers.font import Font
from mgtools.readers.locale import Locale
from mgtools.readers.palette import Palette
from mgtools.readers.sprite import Sprite
from mgtools.readers.unknown import UnknownFile


class Resource:

    __game: Game = Game.UNKNOWN
    __platform: Platform = Platform.UNKNOWN

    __files: list[File] = []

    @property
    def file_count(self) -> int:
        return len(self.__files)

    def __init__(self, game: Game, platform: Platform) -> None:
        self.__game = game
        self.__platform = platform

    def __str__(self) -> str:
        return f"Resource(game={self.__game.name}, platform={self.__platform.name}, files_count={self.file_count})"

    @staticmethod
    def from_file(file_path: Path) -> Resource:
        with open(file_path, "rb") as f:
            resource_magic = f.read(2)

            if resource_magic == RESOURCE_MAGIC:
                resource_game = Game.MG1
                resource_files_count = RESOURCE_FILES_COUNT
            else:
                raise ValueError("Cannot determine game from resource magic.")

            resource_platform = Platform(int.from_bytes(f.read(2)))

            res = Resource(resource_game, resource_platform)

            for idx in range(resource_files_count):
                res.__read_chunk(idx, f)

        return res

    def __read_chunk(self, index, reader) -> None:
        match self.__game:
            case Game.MG1:
                file_type = FILE_TYPE_MAP.get(index, FileType.UNKNOWN)
            case _:
                raise ValueError(f"Unsupported game: {self.__game}")

        match file_type:
            case FileType.SPRITE:
                sprite = Sprite.from_stream(reader)
                self.__files.append(sprite)
            case FileType.PALETTE:
                palette = Palette.from_stream(reader)
                self.__files.append(palette)
            case FileType.LOCALE:
                locale = Locale.from_stream(reader)
                self.__files.append(locale)
            case FileType.FONT:
                font = Font.from_stream(reader)
                self.__files.append(font)
            case _:
                file = UnknownFile.from_stream(reader)
                self.__files.append(file)

    def export(self, output_dir: Path, file_index: int, **kwargs) -> None:
        file = self.__files[file_index]

        match self.__game:
            case Game.MG1:
                file_type_map = FILE_TYPE_MAP
                file_name_map = FILE_NAME_MAP
            case _:
                raise ValueError(f"Unsupported game: {self.__game}")

        file_name = file_name_map.get(file_index, f"{file_index:02d}")

        match file_type_map.get(file_index, FileType.UNKNOWN):
            case FileType.SPRITE:
                file_name = f"{file_name}.{EXPORT_SPRITE_EXTENSION}"
                file_path = output_dir / EXPORT_SPRITE_FOLDER

                # Find loaded palette to export alongside sprite
                for other_file in self.__files:
                    if isinstance(file, Sprite) and isinstance(other_file, Palette):
                        file.add_palette(other_file)
                        break
            case FileType.PALETTE:
                file_name = f"{file_name}.{EXPORT_PALETTE_EXTENSION}"
                file_path = output_dir
            case FileType.LOCALE:
                file_name = ""
                file_path = output_dir / EXPORT_LOCALE_FOLDER
            case FileType.FONT:
                file_name = ""
                file_path = output_dir / EXPORT_FONT_FOLDER
            case _:
                file_name = f"{file_name}.{EXPORT_UNKNOWN_EXTENSION}"
                file_path = output_dir / EXPORT_UNKNOWN_FOLDER

        file_path.mkdir(parents=True, exist_ok=True)
        file.export(file_path / file_name, **kwargs)

    def add_from_folder(self, input_dir: Path, file_index: int) -> None:
        match self.__game:
            case Game.MG1:
                data_type_map = DATA_TYPE_MAP
                file_type_map = FILE_TYPE_MAP
                file_name_map = FILE_NAME_MAP
            case _:
                raise ValueError(f"Unsupported game: {self.__game}")

        file_name = file_name_map.get(file_index, f"{file_index:02d}")

        match file_type_map.get(file_index, FileType.UNKNOWN):
            case FileType.SPRITE:
                file_name = f"{file_name}.{EXPORT_SPRITE_EXTENSION}"
                file_path = input_dir / EXPORT_SPRITE_FOLDER

                file = Sprite.from_file(file_path / file_name)
                self.__files.append(file)
            case FileType.PALETTE:
                file_name = f"{file_name}.{EXPORT_PALETTE_EXTENSION}"
                file_path = input_dir

                file = Palette.from_file(file_path / file_name)
                self.__files.append(file)
            case FileType.LOCALE:
                file_path = input_dir / EXPORT_LOCALE_FOLDER

                file = Locale.from_file(file_path)
                self.__files.append(file)
            case FileType.FONT:
                file_path = input_dir / EXPORT_FONT_FOLDER

                file = Font.from_file(file_path)
                self.__files.append(file)
            case _:
                file_name = f"{file_name}.{EXPORT_UNKNOWN_EXTENSION}"
                file_path = input_dir / EXPORT_UNKNOWN_FOLDER
                data_type = data_type_map.get(file_index, DataType.SIMPLE)

                file = UnknownFile.from_file(file_path / file_name, data_type=data_type)
                self.__files.append(file)

    def save(self, output_path: Path) -> None:
        with open(output_path, "wb") as f:
            match self.__game:
                case Game.MG1:
                    f.write(RESOURCE_MAGIC)
                case _:
                    raise ValueError(f"Unsupported game: {self.__game}")

            f.write(self.__platform.value.to_bytes(2))

            for file in self.__files:
                f.write(file.raw_data)
