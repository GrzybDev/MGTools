from pathlib import Path

import pytest

from mgtools.mc.gcx.editable import export_script, import_script
from mgtools.mc.gcx.script import decode_script, encode_script
from mgtools.mc.gcx.strcode import strcode
from mgtools.translation import TranslationFormat

# Dictionary names that hash like built-in ones replace them throughout every other script.
NAMES = {strcode("if"): "jF", strcode("print"): "prioT"}


def test_every_script_rebuilds_byte_for_byte_and_from_its_directory(
    steam_dir: Path, tmp_path: Path, subtests: pytest.Subtests
) -> None:
    paths = sorted(steam_dir.rglob("*.gcx"))
    assert paths, f"{steam_dir} holds no GCX scripts"
    formats = list(TranslationFormat)
    for number, path in enumerate(paths):
        with subtests.test(path.relative_to(steam_dir).as_posix()):
            data = path.read_bytes()
            script = decode_script(data)
            directory = tmp_path / str(number)

            export_script(
                script,
                directory,
                formats[number % len(formats)],
                original=path.name,
                source_language="en",
                names=NAMES if number % 2 else None,
            )

            assert encode_script(script) == data
            assert encode_script(import_script(directory)) == data
