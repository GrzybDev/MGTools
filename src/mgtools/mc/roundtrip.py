"""Checks and text forms shared by the exact round trips of the engine formats."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mgtools.errors import FormatError
from mgtools.fileio import convert_json


def ensure_rebuilds[M](data: bytes, model: M, encode: Callable[[M], bytes], kind: str) -> M:
    """Return model if it encodes back to data exactly, else raise FormatError.

    Args:
        data: The file the model was read from.
        model: The model read from data.
        encode: The function that writes the model back.
        kind: What the file is, as errors name it.
    """
    try:
        rebuilt = encode(model)
    except ValueError as error:
        msg = f"The {kind} holds data this tool cannot keep: {error}"
        raise FormatError(msg) from error
    if rebuilt != data:
        offset = next(
            (i for i, (a, b) in enumerate(zip(data, rebuilt, strict=False)) if a != b),
            min(len(data), len(rebuilt)),
        )
        msg = f"The {kind} holds data this tool cannot keep, at offset {offset:#x}"
        raise FormatError(msg)
    return model


def import_json[M](path: Path, convert: Callable[[Any], M], encode: Callable[[M], bytes]) -> M:
    """Convert a JSON file to a model that encodes, naming the file in any error.

    Args:
        path: The JSON file to read.
        convert: The function that builds the model from the parsed document.
        encode: The function that writes the model, run to refuse one it cannot write.
    """

    def encodable(document: Any) -> M:
        model = convert(document)
        encode(model)
        return model

    return convert_json(path, encodable)


def colour_text(rgba: bytes) -> str:
    """Write a colour as #rrggbbaa.

    Args:
        rgba: The colour's red, green, blue and alpha bytes.
    """
    return f"#{rgba.hex()}"


def parse_colour(text: str) -> bytes:
    """Read a colour written as #rrggbbaa into its RGBA bytes.

    Args:
        text: The colour, as colour_text writes it.
    """
    if not re.fullmatch(r"#[0-9a-fA-F]{8}", text):
        msg = f"{text!r} is not a colour written as #rrggbbaa"
        raise ValueError(msg)
    return bytes.fromhex(text[1:])


def code_text(code: int) -> str:
    """Write a strcode as the eight hex digits the files named after one use.

    Args:
        code: The strcode to write.
    """
    return f"{code:08x}"


def parse_code(text: str) -> int:
    """Read a strcode written in hex digits.

    Args:
        text: The strcode, as code_text writes it.
    """
    return int(text, 16)
