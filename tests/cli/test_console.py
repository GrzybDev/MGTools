import pytest
import typer

from mgtools.cli.console import reports_errors


def test_errors_keep_long_paths_on_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    path = "C:/" + "folder/" * 20 + "page2.png"

    @reports_errors
    def fail() -> None:
        msg = f"{path}: the glyph is wrong"
        raise ValueError(msg)

    with pytest.raises(typer.Exit):
        fail()

    assert f"Error: {path}: the glyph is wrong" in capsys.readouterr().err
