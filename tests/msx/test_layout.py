import pytest

from mgtools.msx.layout import parse_position, position_name


@pytest.mark.parametrize(
    ("position", "name"),
    [((71,), "71"), ((71, 5), "71.005"), ((20, 51, 6), "20.051.006")],
)
def test_positions_are_named_with_padded_indices(position: tuple[int, ...], name: str) -> None:
    assert position_name(position) == name
    assert parse_position(name) == position


@pytest.mark.parametrize("name", ["7.005", "71.5", "71-005", "71.005 copy", ""])
def test_other_names_are_not_positions(name: str) -> None:
    with pytest.raises(ValueError, match="does not name a position"):
        parse_position(name)
