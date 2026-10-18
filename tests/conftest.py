"""The game installs for the tests on real files, skipped when they are not named."""

import os
from pathlib import Path

import pytest


def _install(variable: str) -> Path:
    """Return the game install an environment variable names, skipping the test without one."""
    value = os.environ.get(variable)
    if not value or not Path(value).is_dir():
        pytest.skip(f"{variable} does not name a game install")
    return Path(value)


@pytest.fixture(scope="session")
def steam_dir() -> Path:
    """The METAL GEAR & METAL GEAR 2: Solid Snake install of the Master Collection."""
    return _install("MGTOOLS_STEAM_DIR")


@pytest.fixture(scope="session")
def gog_dir() -> Path:
    """The Metal Gear install of GOG."""
    return _install("MGTOOLS_GOG_DIR")
