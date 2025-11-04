from mgtools.mg1.constants import (
    EXPORT_PALETTE_EXTENSION,
    EXPORT_PALETTE_FOLDER,
    EXPORT_SPRITE_EXTENSION,
    EXPORT_SPRITE_FOLDER,
    EXPORT_UNKNOWN_EXTENSION,
    EXPORT_UNKNOWN_FOLDER,
)
from mgtools.mg1.formats.palette import Palette
from mgtools.mg1.formats.sprite import Sprite
from mgtools.mg1.mappings import FILE_NAME_MAP


def export_file(resource, index, output_dir):
    file = resource.get(index)
    file_name = FILE_NAME_MAP.get(index, f"{index:02d}")
    file_path = output_dir

    if isinstance(file, Sprite):
        file_path = output_dir / EXPORT_SPRITE_FOLDER
        file_path.mkdir(parents=True, exist_ok=True)

        color_palette = resource.get_palette()

        file.set_palette(color_palette)
        file.save(file_path / f"{file_name}.{EXPORT_SPRITE_EXTENSION}")
    elif isinstance(file, Palette):
        file_path = output_dir / EXPORT_PALETTE_FOLDER
        file_path.mkdir(parents=True, exist_ok=True)
        file.save(file_path / f"{file_name}.{EXPORT_PALETTE_EXTENSION}")
    else:
        file_path = output_dir / EXPORT_UNKNOWN_FOLDER
        file_path.mkdir(parents=True, exist_ok=True)

        file.save(file_path / f"{file_name}.{EXPORT_UNKNOWN_EXTENSION}")
