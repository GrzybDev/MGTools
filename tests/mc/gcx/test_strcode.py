import pytest

from mgtools.mc.gcx.strcode import strcode


@pytest.mark.parametrize(
    ("name", "code"),
    [("scenerio", 0x180720), ("ROOT", 0x2A4634), ("time_paradox", 0x5A6ED3)],
)
def test_names_hash_to_the_codes_the_engine_uses(name: str, code: int) -> None:
    assert strcode(name) == code


def test_bits_leaving_the_top_of_24_rotate_back_in_at_the_bottom() -> None:
    assert strcode("\x01" + "\0" * 5) == 1 << 1


@pytest.mark.parametrize("name", ["", "\0"])
def test_names_hashing_to_0_get_1(name: str) -> None:
    assert strcode(name) == 1
