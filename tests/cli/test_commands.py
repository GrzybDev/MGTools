from pathlib import Path

import pytest
from typer.testing import CliRunner

from mgtools.cli import app
from mgtools.mc.cfon import ConsoleFont, encode_font
from mgtools.mc.ctxr import Texture, encode_texture
from mgtools.mc.gcx.nodes import Block, Call, Command, StrCode
from mgtools.mc.gcx.script import Proc, Script, encode_script
from mgtools.mc.gcx.strcode import strcode
from mgtools.mc.keepfont import Keepfont, LatinGlyph, encode_keepfont
from mgtools.mc.la2.codec import encode_layout
from mgtools.mc.la2.model import Layout, Node
from mgtools.mc.sdx import Bank, SoundBanks, encode_sdx
from mgtools.mc.stov import StovString, encode_stov
from mgtools.mc.tnof import Glyph, TnofFont, encode_tnof
from mgtools.mc.tri import Atlas, encode_atlas
from tests.msx.samples import mg1_file

SCRIPT = Script(True, 1, 0, (Proc(1, Block(())),), Block((Call(1),)), (), b"")
ROOT_ONLY = Layout(0, (), (0,) * 5, (Node(1, 0, 0, 1),), (), (), (), (), (), (), (), ())
ASCII_ONLY = ConsoleFont(((0, 0, 1, 1),), {chr(code): 0 for code in range(128)}, "")
NO_TABLES = {b"IA3P": b"", b"TPAT": b"", b"IPAT": b""}
# A small file of each group, and the name its export gets by default.
FILES = {
    "resource": ("english.raw", mg1_file(), "english"),
    "gcx": ("scenerio.gcx", encode_script(SCRIPT), "scenerio"),
    "ctxr": (
        "texture.ctxr",
        encode_texture(Texture(7, 1, 1, (bytes(4),))),
        "texture.png",
    ),
    "tri": ("atlas.tri", encode_atlas(Atlas(1, 1, 0, ())), "atlas.json"),
    "la2": ("layout.la2", encode_layout(ROOT_ONLY), "layout.json"),
    "cfon": ("console.cfon", encode_font(ASCII_ONLY), "console.json"),
    "tnof": (
        "MGS_Font.raw",
        encode_tnof(TnofFont((1, 2, 3), (Glyph(0x41, 1, 1, 0, 0, 2, b"\xff"),))),
        "MGS_Font",
    ),
    "keepfont": (
        "keepfont.raw",
        encode_keepfont(Keepfont(0, (LatinGlyph(1, 0, bytes(24)),), (bytes(576),))),
        "keepfont",
    ),
    "stov": (
        "stovc.bin",
        encode_stov([StovString(1, "en", "Hi")], "stovc"),
        "stovc.xlf",
    ),
    "sdx": (
        "pk001.sdx",
        encode_sdx(SoundBanks((Bank(0, NO_TABLES, (), ()),), b"")),
        "pk001",
    ),
}


def _files(folder: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}


@pytest.mark.parametrize("group", FILES)
def test_exports_import_back_next_to_the_file_keeping_edits_and_the_original(
    tmp_path: Path, group: str
) -> None:
    name, data, exported = FILES[group]
    path = tmp_path / name
    path.write_bytes(data)
    runner = CliRunner()

    export = runner.invoke(app, [group, "export", str(path)])
    exported_files = _files(tmp_path)
    export_again = runner.invoke(app, [group, "export", str(path)])
    files_after_refusal = _files(tmp_path)
    import_ = runner.invoke(app, [group, "import", str(tmp_path / exported)])
    rebuilt = path.read_bytes()
    path.write_bytes(b"an earlier import")
    import_again = runner.invoke(app, [group, "import", str(tmp_path / exported)])

    assert export.exit_code == 0, export.output
    assert export_again.exit_code == 1
    assert "it is kept and nothing was written" in export_again.output
    assert files_after_refusal == exported_files
    assert import_.exit_code == 0, import_.output
    assert "Kept the original as" in import_.output
    assert f"{name}.orig" in import_.output
    assert rebuilt == data
    assert import_again.exit_code == 0, import_again.output
    assert "Kept the original" not in import_again.output
    assert path.read_bytes() == data
    assert path.with_name(f"{name}.orig").read_bytes() == data


def test_texture_exports_refuse_the_settings_of_an_earlier_export(tmp_path: Path) -> None:
    name, data, _ = FILES["ctxr"]
    (tmp_path / name).write_bytes(data)
    (tmp_path / "texture.json").write_text("{}")

    result = CliRunner().invoke(app, ["ctxr", "export", str(tmp_path / name)])

    assert result.exit_code == 1
    assert "texture.json already exists" in result.output
    assert not (tmp_path / "texture.png").exists()


def test_a_folder_imports_from_inside_it_next_to_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "english.raw").write_bytes(mg1_file())
    runner = CliRunner()
    runner.invoke(app, ["resource", "export", str(tmp_path / "english.raw")])
    (tmp_path / "english.raw").unlink()
    monkeypatch.chdir(tmp_path / "english")

    result = runner.invoke(app, ["resource", "import", "."])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "english.raw").read_bytes() == mg1_file()


def test_texts_are_exported_in_the_format_asked_for(tmp_path: Path) -> None:
    (tmp_path / "english.raw").write_bytes(mg1_file())

    result = CliRunner().invoke(
        app, ["resource", "export", str(tmp_path / "english.raw"), "--format", "po"]
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "english" / "text.po").is_file()


def test_exports_can_name_the_codes_as_an_earlier_export_did(tmp_path: Path) -> None:
    (tmp_path / "english.raw").write_bytes(mg1_file())
    runner = CliRunner()
    runner.invoke(app, ["resource", "export", str(tmp_path / "english.raw")])
    font = tmp_path / "english" / "font.json"
    font.write_text(font.read_text(encoding="utf-8").replace("É", "Ś"), "utf-8")

    result = runner.invoke(
        app,
        [
            *("resource", "export", str(tmp_path / "english.raw")),
            *(str(tmp_path / "again"), "--charmap", str(font)),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Ś" in (tmp_path / "again" / "text.xlf").read_text(encoding="utf-8")


def test_resource_exports_can_save_each_glyph_as_its_own_image(tmp_path: Path) -> None:
    (tmp_path / "english.raw").write_bytes(mg1_file())
    runner = CliRunner()

    export = runner.invoke(app, ["resource", "export", str(tmp_path / "english.raw"), "-s"])
    (tmp_path / "english.raw").unlink()
    import_ = runner.invoke(app, ["resource", "import", str(tmp_path / "english")])

    assert export.exit_code == 0, export.output
    assert (tmp_path / "english/font/page0/U+0041.png").is_file()
    assert not (tmp_path / "english/font/page0.png").exists()
    assert import_.exit_code == 0, import_.output
    assert (tmp_path / "english.raw").read_bytes() == mg1_file()


def test_script_exports_name_strcodes_from_the_usable_lines_of_a_dictionary(
    tmp_path: Path,
) -> None:
    script = Script(
        False, 1, 0, (), Block((Command(strcode("lamp"), (StrCode(0x966474),)),)), (), b""
    )
    path = tmp_path / "scenerio.gcx"
    path.write_bytes(encode_script(script))
    dictionary = tmp_path / "names.txt"
    dictionary.write_bytes(
        b"strcode name\n379210 lamp // a light\n966474 open_dor\n000D86 if\n000D86 jF\n"
        b"379210 lamq\n"
    )
    runner = CliRunner()

    exported = runner.invoke(app, ["gcx", "export", str(path), "--dictionary", str(dictionary)])
    listing = (tmp_path / "scenerio" / "script.gcl").read_bytes()
    rebuilt = tmp_path / "rebuilt.gcx"
    imported = runner.invoke(app, ["gcx", "import", str(tmp_path / "scenerio"), str(rebuilt)])

    assert exported.exit_code == 0, exported.output
    assert (
        "names.txt: skipped 4 lines that a listing cannot use:\n"
        "  Line 1: 'strcode' is not a strcode of up to six hex digits\n"
        "  Line 3: open_dor hashes to #14B323, not #966474\n"
        "  Line 5: #000D86 already has the name if\n"
        "  and 1 more\n"
    ) in exported.output
    assert b"main {\n    lamp #966474;\n}" in listing
    assert imported.exit_code == 0, imported.output
    assert rebuilt.read_bytes() == path.read_bytes()


def test_errors_end_the_command_with_a_message_and_write_nothing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "MGS_Font.raw"
    path.write_bytes(b"TNOF")

    result = CliRunner().invoke(app, ["resource", "export", str(path)])

    assert result.exit_code == 1
    assert "Error: Not a resource file of Metal Gear" in result.output
    assert list(tmp_path.iterdir()) == [path]


def test_info_names_the_game_and_what_its_sections_hold(tmp_path: Path) -> None:
    (tmp_path / "english.raw").write_bytes(mg1_file())

    result = CliRunner().invoke(app, ["resource", "info", str(tmp_path / "english.raw")])

    assert result.exit_code == 0, result.output
    assert "Metal Gear, 77 sections" in result.output
    assert "sprite sheet" in result.output
