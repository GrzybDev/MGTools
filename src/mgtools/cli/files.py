"""The command listing the files the engine reads."""

from itertools import groupby
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

from mgtools.cli.commands import input_argument
from mgtools.cli.console import console, reports_errors, warn
from mgtools.mc.manifest import (
    Controller,
    KeyboardLayout,
    Language,
    Region,
    data_folder,
    listed_files,
)


@reports_errors
def files(
    game_dir: Annotated[
        Path,
        input_argument("The folder of METAL GEAR & METAL GEAR 2: Solid Snake", folder=True),
    ],
    language: Annotated[
        Language, typer.Option("--language", "-l", help="The game's language")
    ] = Language.ENGLISH,
    region: Annotated[
        Region | None,
        typer.Option(
            "--region",
            "-r",
            help="The game's region (default: jp for Japanese, else eu, as the launcher passes it)",
            show_default=False,
        ),
    ] = None,
    controller: Annotated[
        Controller, typer.Option("--controller", "-c", help="The controller type")
    ] = Controller.XBOX,
    keyboard_layout: Annotated[
        KeyboardLayout,
        typer.Option(help="The keyboard layout setting, for the kbd controller"),
    ] = KeyboardLayout.A,
) -> None:
    """List the file the game reads for each line of its file and texture lists."""
    region = region or (Region.JAPAN if language is Language.JAPANESE else Region.EUROPE)
    entries = listed_files(game_dir, language, region, controller, keyboard_layout)
    console.print(f"Data folder: {data_folder(language, region)}", highlight=False)
    for list_path, group in groupby(entries, key=lambda entry: entry.list_path):
        lines = list(group)
        width = max(len(entry.id) for entry in lines)
        console.print(f"[bold]{escape(list_path)}[/]")
        for entry in lines:
            file = escape(entry.found) if entry.found else f"[red]missing[/] ({escape(entry.path)})"
            console.print(f"  {escape(entry.id):<{width}}  {file}", highlight=False)
    if missing := sum(entry.found is None for entry in entries):
        warn(f"{missing} of {len(entries)} lines name a file that does not exist")
