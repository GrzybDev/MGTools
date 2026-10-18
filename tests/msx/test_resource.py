import shutil
from pathlib import Path

import pytest
from PIL import Image

from mgtools.errors import FormatError
from mgtools.fileio import read_json, write_json
from mgtools.msx.container import Container, Leaf, decode_node, encode_node
from mgtools.msx.game import Game
from mgtools.msx.images import IndexedImage, decode_image
from mgtools.msx.resource import (
    Section,
    describe_resource,
    export_resource,
    import_resource,
)
from mgtools.translation import TranslationFormat
from tests.msx.samples import (
    MG1_RECTANGLES,
    MG2_BLOCKS,
    MG2_CELLS,
    leaves,
    mg1_file,
    mg2_file,
    mg2_palette,
)


def export(data: bytes, directory: Path) -> None:
    export_resource(data, directory, TranslationFormat.PO)


def leaf(data: bytes, *position: int) -> bytes:
    node = decode_node(data)
    for index in position:
        assert isinstance(node, Container)
        node = node.children[index]
    assert isinstance(node, Leaf)
    return node.data


def palette_colour(path: Path, index: int) -> tuple[int, ...]:
    with Image.open(path) as png:
        palette = png.getpalette()
    assert palette is not None
    return tuple(palette[index * 3 : index * 3 + 3])


def test_an_mg1_file_exports_every_leaf_once_and_imports_back(tmp_path: Path) -> None:
    data = mg1_file()

    export(data, tmp_path)

    assert import_resource(tmp_path) == data
    assert read_json(tmp_path / "resource.json") == {
        "game": "mg1",
        "empty_containers": ["40.001"],
        "colour_choices": {"41.000": {"#000000": 3}},
    }
    assert read_json(tmp_path / "actors.json") == {
        "0": [
            {"sheet": 41, "x": 1, "y": 2, "w": 3, "h": 4},
            {"sheet": 42, "x": 5, "y": 6, "w": 7, "h": 8},
        ]
    }
    assert read_json(tmp_path / "palettes.json") == [["#ff00ff", "#000000", "#c86432", "#000000"]]
    images = {path.name for path in (tmp_path / "images").iterdir()}
    assert images == {"00.002.png", "00.003.png", "00.004.png", "00.005.png"} | {
        "41.000.png",
        "76.000.png",
    }
    raw = {path.name for path in (tmp_path / "raw").iterdir()}
    assert {"00.000.bin", "20.000.001.bin", "40.000.001.bin", "41.001.bin"} <= raw
    assert {"40.002.000.bin", "71.000.bin"} <= raw
    assert not {"40.000.000.bin", "72.000.bin", "74.000.bin", "76.000.bin"} & raw


def test_an_mg2_file_exports_its_cells_and_imports_back(tmp_path: Path) -> None:
    data = mg2_file({})

    export(data, tmp_path)

    assert import_resource(tmp_path) == data
    assert read_json(tmp_path / "cells.json") == [
        [{"slot": 3, "x": 1, "y": 2, "w": 3, "h": 4}],
        [],
    ]
    assert not (tmp_path / "raw" / "00.042.bin").exists()
    assert (tmp_path / "raw" / "00.041.bin").read_bytes() == b"animation"


@pytest.mark.parametrize(
    ("sprite_sets", "sheet", "palette"),
    [
        ({21: {0}, 22: {0}}, 0, 37),
        ({22: {0}}, 0, 40),
        ({17: {35}}, 35, 37),
        ({17: {34}}, 34, 39),
        ({3: {0}, 20: {0}}, 0, 39),
        ({}, 0, 39),
    ],
)
def test_mg2_sprite_sheets_show_the_palettes_of_the_screen_they_are_drawn_on(
    tmp_path: Path, sprite_sets: dict[int, set[int]], sheet: int, palette: int
) -> None:
    export(mg2_file(sprite_sets), tmp_path)

    png = tmp_path / "images" / f"24.{sheet:03d}.png"
    assert palette_colour(png, 96) == mg2_palette(palette)[0]
    assert palette_colour(png, 1) == mg2_palette(41)[1]


def test_mg2_tile_sheets_show_their_area_palette_from_index_192(
    tmp_path: Path,
) -> None:
    export(mg2_file({}), tmp_path)

    assert palette_colour(tmp_path / "images" / "25.000.png", 192) == (33, 0, 0)
    assert palette_colour(tmp_path / "images" / "26.001.png", 193) == (1, 0, 1)


def test_mg2_palettes_must_fit_the_colour_table_where_they_are_loaded(
    tmp_path: Path,
) -> None:
    export(mg2_file({}), tmp_path)
    palettes = read_json(tmp_path / "palettes.json")
    palettes[33] += ["#000000"] * 63
    write_json(tmp_path / "palettes.json", palettes)

    with pytest.raises(
        ValueError, match=r"Palette 33 has 65 colours, .* at index 192, .* room for 64"
    ):
        import_resource(tmp_path)


def test_edited_images_and_rectangles_reach_the_file(tmp_path: Path) -> None:
    export(mg1_file(), tmp_path)
    actors = read_json(tmp_path / "actors.json")
    actors["0"][1]["x"] = 9
    write_json(tmp_path / "actors.json", actors)
    png = Image.new("RGBA", (3, 1))
    png.putdata([(0, 0, 0, 0), (0, 0, 0, 255), (200, 100, 50, 255)])
    png.save(tmp_path / "images" / "41.000.png")

    data = import_resource(tmp_path)

    assert leaf(data, 40, 0, 0) == MG1_RECTANGLES[:8] + b"\x09" + MG1_RECTANGLES[9:]
    assert decode_image(leaf(data, 41, 0)) == IndexedImage(3, 1, bytes([0, 3, 2]))


def test_rgba_copies_of_the_images_import_back_byte_for_byte(tmp_path: Path) -> None:
    data = mg1_file()
    export(data, tmp_path)
    for path in (tmp_path / "images").iterdir():
        with Image.open(path) as png:
            rgba = png.convert("RGBA")
        rgba.save(path)

    assert import_resource(tmp_path) == data


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (encode_node(Container((Container(()),) * 48)), r"Metal Gear 2 \(49\)$"),
        (encode_node(Container((Leaf(b""),) * 77)), r"Metal Gear 2 \(49\)$"),
        (bytes.fromhex("40000009"), "49.: The node at offset 0 runs past"),
    ],
)
def test_files_that_are_not_resource_files_are_refused(
    tmp_path: Path, data: bytes, message: str
) -> None:
    with pytest.raises(FormatError, match=f"Not a resource file of Metal Gear.*{message}"):
        export(data, tmp_path)


@pytest.mark.parametrize(
    ("source", "target", "message"),
    [
        ("raw/71.000.bin", None, "No file holds 71"),
        ("raw/73.000.bin", "raw/74.000.bin", "holds 74.000 twice"),
        (None, "raw/notes.bin", "'notes' does not name a position"),
        (None, "raw/40.001.000.bin", "hold both 40.001 and nodes inside it"),
        (None, "raw/40.001.bin", "40.001 both as a file and as an empty container"),
        ("images/00.002.png", "images/71.001.png", "71.001 holds no image"),
        (None, "raw/77.000.bin", "holds 77.000, but the last section is 76"),
        ("images/76.000.png", None, "holds 76 sections, not 77"),
    ],
)
def test_folders_that_lost_or_gained_files_are_refused(
    tmp_path: Path, source: str | None, target: str | None, message: str
) -> None:
    export(mg1_file(), tmp_path)
    if source and target:
        shutil.copy(tmp_path / source, tmp_path / target)
    elif source:
        (tmp_path / source).unlink()
    elif target:
        (tmp_path / target).touch()

    with pytest.raises(ValueError, match=message):
        import_resource(tmp_path)


def test_exports_refuse_folders_that_hold_files(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("mine")

    with pytest.raises(FileExistsError, match="is not empty"):
        export(mg1_file(), tmp_path)


def test_a_manifest_naming_no_game_is_refused(tmp_path: Path) -> None:
    export(mg1_file(), tmp_path)
    write_json(tmp_path / "resource.json", {"game": "mg3"})

    with pytest.raises(ValueError, match=r"resource\.json: 'mg3' is not a valid Game"):
        import_resource(tmp_path)


def test_errors_in_rectangles_name_their_file(tmp_path: Path) -> None:
    export(mg2_file({}), tmp_path)
    write_json(tmp_path / "cells.json", [[{"slot": 300, "x": 0, "y": 0, "w": 0, "h": 0}]])

    with pytest.raises(ValueError, match=r"cells\.json: Cell group 0: Rectangle 0"):
        import_resource(tmp_path)


def test_sections_are_described_by_what_they_hold() -> None:
    game, sections = describe_resource(mg2_file({}))

    assert game == Game.MG2
    assert len(sections) == 49
    assert sections[0] == Section("animations", 43, 4 + 42 * 13 + 4 + len(MG2_CELLS))
    assert sections[2] == Section("text", 24, len(encode_node(leaves(MG2_BLOCKS))))
