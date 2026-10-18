from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mgtools.mc import ctxr

type Codec = tuple[
    Callable[[bytes], Any],
    Callable[[Any], bytes],
    Callable[[Any, Path], None],
    Callable[[Path], Any],
]

FORMATS: dict[str, tuple[str, Codec]] = {
    ".ctxr": (
        ".png",
        (
            ctxr.decode_texture,
            ctxr.encode_texture,
            ctxr.export_texture,
            ctxr.import_texture,
        ),
    ),
}


@pytest.mark.parametrize("suffix", FORMATS)
def test_every_file_rebuilds_and_imports_back_byte_for_byte(
    steam_dir: Path, tmp_path: Path, subtests: pytest.Subtests, suffix: str
) -> None:
    editable, (decode, encode, export, import_) = FORMATS[suffix]
    files = sorted(steam_dir.rglob(f"*{suffix}"))
    assert files, f"{steam_dir} holds no {suffix} files"
    for index, path in enumerate(files):
        with subtests.test(path.relative_to(steam_dir).as_posix()):
            data = path.read_bytes()
            model = decode(data)
            exported = tmp_path / f"{index}{editable}"

            export(model, exported)

            assert encode(model) == data
            assert encode(import_(exported)) == data
