from pathlib import Path

import pytest

from mgtools.mc.gcx.script import decode_script, encode_script


def test_every_script_rebuilds_byte_for_byte(steam_dir: Path, subtests: pytest.Subtests) -> None:
    paths = sorted(steam_dir.rglob("*.gcx"))
    assert paths, f"{steam_dir} holds no GCX scripts"
    for path in paths:
        with subtests.test(path.relative_to(steam_dir).as_posix()):
            data = path.read_bytes()

            assert encode_script(decode_script(data)) == data
