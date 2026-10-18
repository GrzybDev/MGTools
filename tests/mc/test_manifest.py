from pathlib import Path

import pytest

from mgtools.errors import FormatError
from mgtools.mc.manifest import (
    Controller,
    KeyboardLayout,
    Language,
    ListedFile,
    Region,
    data_folder,
    listed_files,
)

MANIFEST = "fr/stage/mg1/manifest.txt"
ENGLISH_LINE = "fr/stage/mg1/cache/english.raw,fr/x.raw,cache/00861c98.raw\n"
CANDIDATES = [
    "fr/stage/mg1/cache/ovr_stm/ctrltype_kbd/type_b/english.raw",
    "fr/stage/mg1/cache/ovr_stm/ctrltype_kbd/ovr_eu/english.raw",
    "fr/stage/mg1/cache/ovr_stm/ctrltype_kbd/english.raw",
    "fr/stage/mg1/cache/ovr_stm/ovr_eu/english.raw",
    "fr/stage/mg1/cache/ovr_stm/english.raw",
    "fr/stage/mg1/cache/ovr_eu/english.raw",
    "fr/stage/mg1/cache/english.raw",
]


def _create(game_dir: Path, *paths: str, text: str = "") -> None:
    for path in paths:
        (game_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (game_dir / path).write_text(text, "utf-8")


def _found(game_dir: Path, controller: Controller = Controller.XBOX) -> list[str | None]:
    entries = listed_files(game_dir, Language.ENGLISH, Region.EUROPE, controller, KeyboardLayout.B)
    return [entry.found for entry in entries]


@pytest.mark.parametrize(
    ("language", "region", "folder"),
    [
        (Language.ENGLISH, Region.USA, "fr"),
        (Language.ENGLISH, Region.EUROPE, "fr"),
        (Language.GERMAN, Region.EUROPE, "gr"),
        (Language.SPANISH, Region.USA, "sp"),
        (Language.ENGLISH, Region.JAPAN, "jp"),
        (Language.JAPANESE, Region.EUROPE, "us"),
        (Language.RUSSIAN, Region.EUROPE, "us"),
    ],
)
def test_the_data_folder_follows_language_and_region(
    language: Language, region: Region, folder: str
) -> None:
    assert data_folder(language, region) == folder


def test_the_most_specific_override_that_exists_is_read(tmp_path: Path) -> None:
    _create(tmp_path, MANIFEST, text=ENGLISH_LINE)
    assert _found(tmp_path, Controller.KEYBOARD) == [None]

    for path in reversed(CANDIDATES):
        _create(tmp_path, path)

        assert _found(tmp_path, Controller.KEYBOARD) == [path]


def test_other_controllers_skip_the_keyboard_folders(tmp_path: Path) -> None:
    _create(tmp_path, MANIFEST, text=ENGLISH_LINE)
    _create(tmp_path, *CANDIDATES)
    assert _found(tmp_path) == ["fr/stage/mg1/cache/ovr_stm/ovr_eu/english.raw"]

    _create(tmp_path, "fr/stage/mg1/cache/ovr_stm/ctrltype_xs/english.raw")

    assert _found(tmp_path) == ["fr/stage/mg1/cache/ovr_stm/ctrltype_xs/english.raw"]


def test_overrides_of_a_file_at_the_top_stay_in_the_game_folder(
    tmp_path: Path,
) -> None:
    _create(tmp_path, MANIFEST, text="top.raw,x,cache/1.raw")
    _create(tmp_path, "ovr_eu/top.raw")

    assert _found(tmp_path) == ["ovr_eu/top.raw"]


def test_scripts_are_read_from_their_bp_folder_when_it_holds_them(
    tmp_path: Path,
) -> None:
    script = "assets/gcx/fr/scenerio_stage_init.gcx"
    _create(tmp_path, "fr/stage/init/manifest.txt", text=f"{script},x,cache/00180720.gcx")
    _create(tmp_path, script)
    assert _found(tmp_path) == [script]

    _create(tmp_path, "assets/gcx/fr/_bp/scenerio_stage_init.gcx")
    assert _found(tmp_path) == ["assets/gcx/fr/_bp/scenerio_stage_init.gcx"]

    _create(tmp_path, "assets/gcx/fr/_bp/ovr_stm/scenerio_stage_init.gcx")
    assert _found(tmp_path) == ["assets/gcx/fr/_bp/ovr_stm/scenerio_stage_init.gcx"]


def test_textures_are_read_from_their_win_folder_with_overrides_around_it(
    tmp_path: Path,
) -> None:
    line = "textures/flatlist/001dcfc8.ctxr,x,fr/slot/memcard/cache/00fdea15/1.ctxr"
    _create(tmp_path, "fr/slot/memcard/bp_assets.txt", text=line)
    _create(tmp_path, "textures/flatlist/001dcfc8.ctxr")
    assert _found(tmp_path) == [None]

    _create(tmp_path, "textures/flatlist/_win/001dcfc8.ctxr")
    assert _found(tmp_path) == ["textures/flatlist/_win/001dcfc8.ctxr"]

    _create(tmp_path, "textures/flatlist/ovr_stm/_win/001dcfc8.ctxr")
    assert _found(tmp_path) == ["textures/flatlist/ovr_stm/_win/001dcfc8.ctxr"]


def test_lines_of_other_video_modes_and_data_folders_are_left_out(
    tmp_path: Path,
) -> None:
    lines = [
        "a/one.raw,x,cache/1.raw",
        "",
        "b/two.raw,x,cache/2.raw,50HZ",
        "c/three.raw,x,cache/3.raw,60HZ",
    ]
    _create(tmp_path, MANIFEST, text="\n".join(lines))
    _create(tmp_path, "gr/stage/mg1/manifest.txt", text="d/four.raw,x,cache/4.raw")
    _create(tmp_path, "c/three.raw")

    entries = listed_files(tmp_path, Language.ENGLISH, Region.USA, Controller.PS5)

    assert entries == [
        ListedFile(MANIFEST, "cache/1.raw", "a/one.raw", None),
        ListedFile(MANIFEST, "cache/3.raw", "c/three.raw", "c/three.raw"),
    ]


def test_a_line_with_too_few_columns_is_reported(tmp_path: Path) -> None:
    _create(tmp_path, MANIFEST, text="a/one.raw,x,cache/1.raw\na/two.raw,x\n")

    with pytest.raises(FormatError, match=f"Line 2 of {MANIFEST} has 2 columns"):
        listed_files(tmp_path, Language.ENGLISH, Region.USA, Controller.PS5)
