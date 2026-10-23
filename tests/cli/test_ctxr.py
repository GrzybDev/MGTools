"""The texture commands on folders and wildcard patterns."""

import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mgtools.cli import app, run
from mgtools.mc.ctxr import Texture, encode_texture, mipmaps


def _texture(seed: int) -> bytes:
    level0 = bytes(range(seed, seed + 16))
    return encode_texture(Texture(7, 2, 2, (level0, *mipmaps(level0, 2, 2))))


def _write(files: dict[Path, bytes]) -> None:
    for path, data in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _tree(folder: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}


def _mgtools(monkeypatch: pytest.MonkeyPatch, *args: str) -> object:
    """Run mgtools as its console script does, which expands arguments itself on Windows."""
    monkeypatch.setattr(sys, "argv", ["mgtools", *args])
    with pytest.raises(SystemExit) as exit_:
        run()
    return exit_.value.code


def test_a_folder_exports_its_textures_next_to_them_and_imports_them_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    textures = {Path("t/a.ctxr"): _texture(0), Path("t/b.ctxr"): _texture(100)}
    _write({**textures, Path("t/nested/c.ctxr"): _texture(200), Path("t/x.txt"): b"notes"})
    runner = CliRunner()

    export = runner.invoke(app, ["ctxr", "export", "t"])
    exported = sorted(path.relative_to("t").as_posix() for path in _tree(Path("t")))
    Path("t/stray.png").write_bytes(Path("t/a.png").read_bytes())
    import_ = runner.invoke(app, ["ctxr", "import", "t"])

    assert export.exit_code == 0, export.output
    assert export.output.count("Exported") == 2
    assert exported == [
        *("a.ctxr", "a.json", "a.png", "b.ctxr", "b.json", "b.png"),
        *("nested/c.ctxr", "x.txt"),
    ]
    assert import_.exit_code == 0, import_.output
    assert import_.output.count("Kept the original as") == 2
    assert not Path("t/stray.ctxr").exists()
    for path, data in textures.items():
        assert path.read_bytes() == data
        assert path.with_name(f"{path.name}.orig").read_bytes() == data


@pytest.mark.parametrize(
    ("source", "output"),
    [
        ("game/**/*.ctxr", "png"),
        pytest.param(
            "~/game/**/*.ctxr",
            "%PNG_FOLDER%",
            marks=pytest.mark.skipif(
                os.name != "nt", reason="POSIX shells expand ~ and variables before mgtools starts"
            ),
        ),
    ],
)
def test_a_pattern_converts_to_a_folder_keeping_the_layout_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str, output: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # where ~ leads on Windows
    monkeypatch.setenv("PNG_FOLDER", "png")
    textures = {Path("game/_win/a.ctxr"): _texture(0), Path("game/ovr/_win/a.ctxr"): _texture(50)}
    _write(textures)

    export = _mgtools(monkeypatch, "ctxr", "export", source, output)
    import_ = _mgtools(monkeypatch, "ctxr", "import", "png/**/*.png", "rebuilt")

    assert export == 0
    assert sorted(path.as_posix() for path in Path("png").rglob("*.png")) == [
        "png/_win/a.png",
        "png/ovr/_win/a.png",
    ]
    assert import_ == 0
    assert _tree(Path("rebuilt")) == {
        "rebuilt" / path.relative_to("game"): data for path, data in textures.items()
    }


def test_a_pattern_that_names_a_texture_by_two_paths_converts_it_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    texture = _texture(0)
    _write({Path("t/a.ctxr"): texture})
    Path("t/x").mkdir()
    Path("t/y").mkdir()
    runner = CliRunner()

    export = runner.invoke(app, ["ctxr", "export", "t/*/../*.ctxr"])
    import_ = runner.invoke(app, ["ctxr", "import", "t/*/../*.png"])

    assert export.exit_code == 0, export.output
    assert export.output.count("Exported") == 1
    assert import_.exit_code == 0, import_.output
    assert import_.output.count("Imported") == 1
    assert Path("t/a.ctxr").read_bytes() == Path("t/a.ctxr.orig").read_bytes() == texture


def test_two_textures_that_would_be_written_to_one_file_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write({Path("t/x/a.ctxr"): _texture(0), Path("t/y/a.ctxr"): _texture(100)})
    Path("png/y").mkdir(parents=True)
    try:
        Path("png/x").symlink_to(Path("png/y").absolute(), target_is_directory=True)
    except OSError:
        pytest.skip("This system does not allow creating symbolic links")

    result = CliRunner().invoke(
        app, ["ctxr", "export", "t/*/a.ctxr", "png"], env={"COLUMNS": "200"}
    )

    assert result.exit_code == 2
    assert (
        f"{Path('t/x/a.ctxr')} and {Path('t/y/a.ctxr')} would both be written to" in result.output
    )
    assert not any(Path("png/y").iterdir())


@pytest.mark.parametrize(
    ("other_file", "data", "message"),
    [
        (
            "t/b.json",
            b"{}",
            f"{Path('t/b.json')} already exists; it is kept and nothing was written",
        ),
        ("t/c.ctxr", b"RXTT" + _texture(0)[4:], f"{Path('t/c.ctxr')}: Not a TXTR texture"),
    ],
)
def test_an_existing_target_or_a_broken_texture_stops_an_export_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, other_file: str, data: bytes, message: str
) -> None:
    monkeypatch.chdir(tmp_path)
    _write({Path("t/a.ctxr"): _texture(0), Path("t/b.ctxr"): _texture(100), Path(other_file): data})
    files = _tree(Path("t"))

    result = CliRunner().invoke(app, ["ctxr", "export", "t/?.ctxr"])

    assert result.exit_code == 1
    assert message in result.output
    assert _tree(Path("t")) == files


def test_broken_settings_stop_an_import_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write({Path("t/a.ctxr"): _texture(0), Path("t/b.ctxr"): _texture(100)})
    runner = CliRunner()
    runner.invoke(app, ["ctxr", "export", "t"])
    Path("t/b.json").write_text('{"version": 9, "mipmaps": true}')
    files = _tree(Path("t"))

    result = runner.invoke(app, ["ctxr", "import", "t"])

    assert result.exit_code == 1
    assert f"{Path('t/b.json')}: TXTR version 9 is not supported" in result.output
    assert _tree(Path("t")) == files


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["export", "t/*.dds"], f"{Path('t/*.dds')} matches no file"),
        (["export", "t/*"], f"{Path('t/*')} matches {Path('t/x.txt')}, which is not a .ctxr file"),
        (["export", "t/missing.ctxr"], f"{Path('t/missing.ctxr')} does not exist"),
        (["import", "t"], "t holds no .png file with its .json settings beside it"),
        (["export", "t", "t/x.txt"], f"{Path('t/x.txt')} is a file, not a folder"),
        (["export", "t/a.ctxr", "t"], "t is a folder, not a .png file"),
        (
            ["export", "t/a.ctxr", "t/b.ctxr"],
            f"{Path('t/b.ctxr')} is a .ctxr file like the input, not a .png file",
        ),
    ],
)
def test_sources_and_outputs_that_name_nothing_to_convert_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], message: str
) -> None:
    monkeypatch.chdir(tmp_path)
    _write({Path("t/a.ctxr"): _texture(0), Path("t/x.txt"): b"notes"})
    files = _tree(Path("t"))

    # Wide enough that Typer's error panel keeps each message on one line.
    result = CliRunner().invoke(app, ["ctxr", *args], env={"COLUMNS": "200"})

    assert result.exit_code == 2
    assert message in result.output
    assert _tree(Path("t")) == files
