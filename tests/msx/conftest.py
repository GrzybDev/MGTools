"""The MSX resource files of the game installs, for the tests on real files."""

from pathlib import Path

import pytest


@pytest.fixture(params=["steam_dir", "gog_dir"])
def resource_files(request: pytest.FixtureRequest) -> list[Path]:
    """Every MSX resource file of one game install.

    Args:
        request: The request whose param names the fixture of the install.
    """
    install: Path = request.getfixturevalue(request.param)
    files = sorted([*install.glob("Resource/*.bin"), *install.glob("*/stage/mg?/cache/**/*.raw")])
    assert files, f"{install} holds no MSX resource files"
    return files
