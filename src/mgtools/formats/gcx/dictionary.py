from pathlib import Path


def load_dictionary(path: Path) -> dict[int, str]:
    """Load a strcode dictionary file.

    Format: one entry per line, hex_strcode<whitespace>name
    Uses EUC-JP encoding.
    """
    result: dict[int, str] = {}
    try:
        text = path.read_text(encoding="euc-jp")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8")

    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                sc = int(parts[0], 16)
                name = parts[1]
                result[sc] = name
            except ValueError:
                continue
    return result
