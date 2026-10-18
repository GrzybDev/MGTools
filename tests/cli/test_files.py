from pathlib import Path

from typer.testing import CliRunner

from mgtools.cli import app


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")


def test_japanese_lists_come_from_the_jp_folder_and_missing_files_are_counted(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "jp/stage/demo/manifest.txt",
        "jp/stage/demo/cache/title.raw,jp/a.raw,cache/0000000a.raw\n"
        "jp/stage/demo/cache/gone.raw,jp/b.raw,cache/0000000b.raw\n",
    )
    _write(tmp_path / "jp/stage/demo/cache/title.raw")
    # The folder a Japanese game outside region jp reads.
    _write(
        tmp_path / "us/stage/demo/manifest.txt",
        "us/stage/demo/cache/title.raw,us/a.raw,cache/0000000c.raw\n",
    )

    result = CliRunner().invoke(app, ["files", str(tmp_path), "--language", "jp"])

    assert result.exit_code == 0, result.output
    assert "Data folder: jp" in result.output
    assert "cache/0000000a.raw  jp/stage/demo/cache/title.raw" in result.output
    assert "cache/0000000b.raw  missing (jp/stage/demo/cache/gone.raw)" in result.output
    assert "0000000c" not in result.output
    assert "Warning: 1 of 2 lines name a file that does not exist" in result.output
