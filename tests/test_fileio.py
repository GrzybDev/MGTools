import codecs
import os
import stat
from pathlib import Path

import pytest

from mgtools.fileio import (
    atomic_writer,
    convert_json,
    read_json,
    write_atomically,
    write_json,
)

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")


def test_a_failed_write_keeps_the_old_file(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(b"old")

    with pytest.raises(RuntimeError), atomic_writer(path) as stream:
        stream.write(b"new")
        raise RuntimeError

    assert path.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [path]


def test_writes_create_the_missing_folders(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "file.bin"

    write_atomically(path, b"data")

    assert path.read_bytes() == b"data"


@posix_only
def test_new_files_get_the_usual_permissions(tmp_path: Path) -> None:
    umask = os.umask(0o022)
    try:
        write_atomically(tmp_path / "file.bin", b"data")
    finally:
        os.umask(umask)

    assert stat.S_IMODE((tmp_path / "file.bin").stat().st_mode) == 0o644


@posix_only
def test_replaced_files_keep_their_permissions(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(b"old")
    path.chmod(0o640)

    write_atomically(path, b"new")

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_json_is_indented_utf_8_that_keeps_its_characters(tmp_path: Path) -> None:
    path = tmp_path / "glyphs.json"
    value = {"char": "Ż", "widths": [8, 12]}

    write_json(path, value)

    assert path.read_bytes() == (
        '{\n  "char": "Ż",\n  "widths": [\n    8,\n    12\n  ]\n}\n'.encode()
    )
    assert read_json(path) == value


def test_json_saved_with_a_byte_order_mark_is_read(tmp_path: Path) -> None:
    path = tmp_path / "edited.json"
    path.write_bytes(codecs.BOM_UTF8 + '{"char": "ł"}'.encode())

    assert read_json(path) == {"char": "ł"}


@pytest.mark.parametrize("data", [b'{"width": 8,}', b"\xff{}"])
def test_unreadable_json_names_the_file(tmp_path: Path, data: bytes) -> None:
    path = tmp_path / "broken.json"
    path.write_bytes(data)

    with pytest.raises(ValueError, match=r"Cannot read .*broken\.json"):
        read_json(path)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('{"height": 8}', "missing 'width'"),
        ("[8, 12]", "list indices must be integers"),
        ('{"width": -1}', "a width must be positive"),
    ],
)
def test_conversion_errors_name_the_file(tmp_path: Path, text: str, message: str) -> None:
    def width(document: dict[str, int]) -> int:
        if document["width"] < 0:
            msg = "a width must be positive"
            raise ValueError(msg)
        return document["width"]

    path = tmp_path / "glyph.json"
    path.write_text(text)

    with pytest.raises(ValueError, match=rf"glyph\.json: {message}"):
        convert_json(path, width)
