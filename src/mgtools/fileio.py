"""Writing files atomically, and reading the JSON and images people edit."""

import json
import os
import stat
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

from PIL import Image

ORIGINAL_SUFFIX = ".orig"
"""The suffix of the originals that replacing a file keeps."""


@contextmanager
def atomic_writer(path: Path) -> Iterator[BinaryIO]:
    """Open a temporary file that replaces path only when the block succeeds.

    The file it replaces is kept where original_to_keep says.

    Args:
        path: The file to create or replace.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "wb") as stream:
            # mkstemp makes files only their owner can read; keep the usual ones.
            Path(temporary).chmod(_mode(path))
            yield stream
        # Moved aside only once the new data is complete, so a failure keeps the file in place.
        if (original := original_to_keep(path)) is not None:
            path.rename(original)
        try:
            Path(temporary).replace(path)
        except BaseException:
            if original is not None:
                original.rename(path)
            raise
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_atomically(path: Path, data: bytes) -> None:
    """Write data to path through a temporary file.

    Args:
        path: The file to create or replace.
        data: The file's new contents.
    """
    with atomic_writer(path) as stream:
        stream.write(data)


def original_to_keep(path: Path) -> Path | None:
    """Return where replacing path keeps the file there, or None when it keeps none.

    The first file replaced is kept beside path as <name>.orig; later ones are not kept, so
    the .orig stays the file as it was before the first replacement.

    Args:
        path: The file to replace.
    """
    original = path.with_name(path.name + ORIGINAL_SUFFIX)
    return original if path.is_file() and not original.exists() else None


def write_png(path: Path, image: Image.Image, **options: Any) -> None:
    """Save an image as a PNG through a temporary file.

    Args:
        path: The file to create or replace.
        image: The image to save.
        **options: The PNG options Image.save takes.
    """
    with atomic_writer(path) as stream:
        image.save(stream, "PNG", **options)


def read_image(path: Path, size: tuple[int, int] | None = None) -> Image.Image:
    """Read an image, refusing one that is not of the given size.

    Args:
        path: The image to read.
        size: The width and height it must have, or None for any.
    """
    with Image.open(path) as image:
        image.load()
    if size and image.size != size:
        msg = f"{path} is {image.width}x{image.height} pixels, not {size[0]}x{size[1]}"
        raise ValueError(msg)
    return image


def write_json(path: Path, value: object) -> None:
    """Write a value as indented UTF-8 JSON that keeps non-ASCII characters.

    Args:
        path: The file to create or replace.
        value: The value to write, made of what json.dumps takes.
    """
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    write_atomically(path, text.encode())


def read_json(path: Path) -> Any:
    """Read a JSON file, with or without the byte order mark some editors add.

    Args:
        path: The file to read.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as error:
        msg = f"Cannot read {path}: {error}"
        raise ValueError(msg) from error


def convert_json[T](path: Path, convert: Callable[[Any], T]) -> T:
    """Convert a JSON file, naming it in any error, a wrong shape included.

    Args:
        path: The file to read.
        convert: Return the converted value of the file's JSON value.
    """
    value = read_json(path)
    try:
        return convert(value)
    except KeyError as error:
        msg = f"{path}: missing {error}"
        raise ValueError(msg) from error
    except (LookupError, TypeError, AttributeError, ValueError) as error:
        msg = f"{path}: {error}"
        raise ValueError(msg) from error


def is_index(value: object, count: int) -> bool:
    """Tell whether a value read from JSON is an int from 0 up to count - 1.

    Args:
        value: The value to check.
        count: The number of valid indices.
    """
    return type(value) is int and 0 <= value < count


def _mode(path: Path) -> int:
    """Return the permissions of the file being replaced, or those of a new file."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask
