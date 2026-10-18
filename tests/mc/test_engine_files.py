"""The engine formats on every file of the Master Collection install."""

import zlib
from pathlib import Path

import pytest

from mgtools.mc.keepfont import (
    decode_keepfont,
    encode_keepfont,
    export_keepfont,
    import_keepfont,
)
from mgtools.mc.stov import decode_stov, encode_stov, export_stov, import_stov
from mgtools.mc.tnof import decode_tnof, encode_tnof, export_tnof, import_tnof
from mgtools.translation import TranslationFormat


def _files(install: Path, pattern: str) -> list[Path]:
    files = sorted(install.glob(pattern))
    assert files, f"{install} holds no {pattern}"
    return files


def _built_in_font(steam_dir: Path) -> bytes:
    """Return the TNOF font METAL GEAR.exe carries as a gzip member."""
    exe = (steam_dir / "METAL GEAR.exe").read_bytes()
    # The member's file name follows its 10-byte header.
    start = exe.index(b"MGS_Font_nht.raw\0") - 10
    return zlib.decompressobj(zlib.MAX_WBITS | 16).decompress(exe[start:])


def test_every_tnof_font_rebuilds_and_imports_back(
    steam_dir: Path, tmp_path: Path, subtests: pytest.Subtests
) -> None:
    fonts = {
        path.name: path.read_bytes() for path in _files(steam_dir, "EngineSupport/Fonts/*.raw")
    }
    fonts["METAL GEAR.exe MGS_Font_nht.raw"] = _built_in_font(steam_dir)
    for index, (name, data) in enumerate(fonts.items()):
        with subtests.test(name):
            font = decode_tnof(data)
            assert encode_tnof(font) == data
            export_tnof(font, tmp_path / str(index))
            assert encode_tnof(import_tnof(tmp_path / str(index))) == data


def test_every_keepfont_rebuilds_and_imports_back(
    steam_dir: Path, tmp_path: Path, subtests: pytest.Subtests
) -> None:
    for path in _files(steam_dir, "assets/raw/*/keepfont*.raw"):
        with subtests.test(path.name):
            data = path.read_bytes()
            font = decode_keepfont(data)
            assert encode_keepfont(font) == data
            export_keepfont(font, tmp_path / path.stem)
            assert encode_keepfont(import_keepfont(tmp_path / path.stem)) == data


@pytest.mark.parametrize("fmt", list(TranslationFormat))
def test_every_string_table_rebuilds_and_imports_back(
    steam_dir: Path, tmp_path: Path, subtests: pytest.Subtests, fmt: TranslationFormat
) -> None:
    for path in _files(steam_dir, "EngineSupport/stov*.bin"):
        with subtests.test(path.name):
            data = path.read_bytes()
            strings = decode_stov(data, path.name)
            assert encode_stov(strings, path.name) == data
            document = tmp_path / path.with_suffix(fmt.suffix).name
            export_stov(strings, document, fmt, path.name)
            assert encode_stov(import_stov(document), path.name) == data
