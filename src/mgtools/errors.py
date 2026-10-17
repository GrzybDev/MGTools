"""Errors shared by the file formats."""

from collections.abc import Iterator
from contextlib import contextmanager


class FormatError(ValueError):
    """Raised when data does not follow the file format it is read as."""


@contextmanager
def located(where: object) -> Iterator[None]:
    """Put where before the message of a ValueError raised within, keeping its kind.

    Args:
        where: What the block works on, such as a path or an index.
    """
    try:
        yield
    except ValueError as error:
        kind = FormatError if isinstance(error, FormatError) else ValueError
        msg = f"{where}: {error}"
        raise kind(msg) from error
