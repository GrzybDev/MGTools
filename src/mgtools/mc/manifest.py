"""Which file the engine reads for each line of its file lists.

The engine takes the lists of each stage and slot page from the data folder of
its language and region: manifest.txt, whose lines are "path,console path,id"
with an optional video mode as a fourth column, and bp_assets.txt, which names
textures the same way. It reads a script from the _bp folder beside its path
when there is one there, a texture from the _win folder beside its path, and in
both cases the first file that exists among the override folders, from the most
specific down to the path itself.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from mgtools.errors import FormatError


class Language(StrEnum):
    """The languages the launcher passes with -lan."""

    ENGLISH = "en"
    JAPANESE = "jp"
    FRENCH = "fr"
    GERMAN = "gr"
    ITALIAN = "it"
    PORTUGUESE = "pr"
    SPANISH = "sp"
    DUTCH = "du"
    RUSSIAN = "ru"


class Region(StrEnum):
    """The regions the launcher passes with -region."""

    USA = "us"
    JAPAN = "jp"
    EUROPE = "eu"


class Controller(StrEnum):
    """The controller types the launcher passes with -ctrltype."""

    PS5 = "ps5"
    PS4 = "ps4"
    XBOX = "xbox"
    SWITCH = "nx"
    STEAM_DECK = "stmd"
    KEYBOARD = "kbd"


class KeyboardLayout(StrEnum):
    """The keyboard layout setting, which picks an override folder for keyboards."""

    A = "a"
    B = "b"


@dataclass(frozen=True, slots=True)
class ListedFile:
    """A line of a file list and the file the engine reads for it."""

    list_path: str
    """The manifest.txt or bp_assets.txt holding the line, from the game folder."""
    id: str
    """The third column, the id the engine knows the file by."""
    path: str
    """The first column, the path the line names."""
    found: str | None
    """The file the engine reads, from the game folder; None when none exists."""


_DATA_FOLDERS = {
    Language.ENGLISH: "fr",
    Language.FRENCH: "fr",
    Language.GERMAN: "gr",
    Language.ITALIAN: "it",
    Language.SPANISH: "sp",
}


def data_folder(language: Language, region: Region) -> str:
    """Return the folder of the lists the engine reads in a language and region.

    Args:
        language: The language the game runs in.
        region: The region the game runs in.
    """
    if region is Region.JAPAN:
        return "jp"
    return _DATA_FOLDERS.get(language, "us")


def listed_files(
    game_dir: Path,
    language: Language,
    region: Region,
    controller: Controller,
    keyboard_layout: KeyboardLayout = KeyboardLayout.A,
) -> list[ListedFile]:
    """Return every line the engine loads from its lists, with the file it reads.

    Args:
        game_dir: The game's folder, which holds the data folders.
        language: The language the game runs in.
        region: The region the game runs in.
        controller: The controller type, which picks override folders.
        keyboard_layout: The keyboard layout, which picks an override folder for keyboards.
    """
    folder = data_folder(language, region)
    lists = sorted(
        list_path
        for name in ("manifest.txt", "bp_assets.txt")
        for list_path in game_dir.glob(f"{folder}/*/*/{name}")
    )
    entries = []
    for list_path in lists:
        relative = list_path.relative_to(game_dir).as_posix()
        for number, line in enumerate(list_path.read_text("utf-8").splitlines(), 1):
            fields = line.split(",")
            if not line or (len(fields) > 3 and fields[3] != "60HZ"):
                continue
            if len(fields) < 3:
                msg = f"Line {number} of {relative} has {len(fields)} columns, not 3 or 4"
                raise FormatError(msg)
            path = fields[0]
            if list_path.name == "bp_assets.txt":
                path = _insert(path, "_win/")
            elif ".gcx" in path and (game_dir / _insert(path, "_bp/")).is_file():
                path = _insert(path, "_bp/")
            candidates = _candidates(path, region, controller, keyboard_layout)
            file = next((c for c in candidates if (game_dir / c).is_file()), None)
            entries.append(ListedFile(relative, fields[2], fields[0], file))
    return entries


def _candidates(
    path: str, region: Region, controller: Controller, keyboard_layout: KeyboardLayout
) -> list[str]:
    """Return the paths the engine tries for a file of a list, in its order."""
    regional = f"ovr_{region}/"
    kind = "xs" if controller is Controller.XBOX else controller
    controls = f"ovr_stm/ctrltype_{kind}/"
    folders = [
        controls + regional,
        controls,
        "ovr_stm/" + regional,
        "ovr_stm/",
        regional,
    ]
    if controller is Controller.KEYBOARD:
        folders.insert(0, f"ovr_stm/ctrltype_kbd/type_{keyboard_layout}/")
    return [*(_insert(path, folder) for folder in folders), path]


def _insert(path: str, folders: str) -> str:
    """Insert folders before the file name of path, or before its _win folder."""
    directory, slash, name = path.rpartition("/")
    if directory.endswith("/_win"):
        directory, name = directory.removesuffix("/_win"), f"_win/{name}"
    return f"{directory}{slash}{folders}{name}"
