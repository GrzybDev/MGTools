from pathlib import Path

import pytest
from PIL import Image

from mgtools.msx.resource import export_resource, import_resource
from mgtools.translation import TranslationFormat


def flatten_images(directory: Path) -> int:
    """Save every indexed image that draws each colour with one index as RGBA, as editors do.

    Args:
        directory: The resource export whose images to save.

    Returns:
        How many images were saved.
    """
    flattened = 0
    for path in (directory / "images").glob("*.png"):
        with Image.open(path) as png:
            palette = png.getpalette() or []
            drawn = set(png.tobytes()) - {0}
            colours = {tuple(palette[index * 3 : index * 3 + 3]) for index in drawn}
            if png.mode != "P" or len(colours) < len(drawn):
                continue
            rgba = png.convert("RGBA")
        rgba.save(path)
        flattened += 1
    return flattened


def test_every_resource_file_imports_back_byte_for_byte_also_from_rgba_images(
    resource_files: list[Path], subtests: pytest.Subtests, tmp_path: Path
) -> None:
    for number, path in enumerate(resource_files):
        with subtests.test(path.as_posix()):
            data = path.read_bytes()
            directory = tmp_path / str(number)

            export_resource(data, directory, TranslationFormat.XLIFF2)

            assert import_resource(directory) == data
            assert flatten_images(directory) > 100
            assert import_resource(directory) == data
