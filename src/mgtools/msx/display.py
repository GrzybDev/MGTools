"""What the MSX games do with the strings of their texts.

Each string gets notes for translators: what its block holds, its MG1 style, its
size, and how the game wraps it or how wide it may be. A translation is checked
for what keeps the game from showing it: characters the fonts lack, and words,
lines and pages longer than the message window holds.
"""

import re
from collections.abc import Iterator

from mgtools.msx.charset import PLACEHOLDERS, Charset
from mgtools.msx.font import Font, Page
from mgtools.msx.game import Game

_DESCRIPTIONS = {
    Game.MG1: {
        3: "Prisoners, hostages and other people",
        4: "Guards, item pick-ups, broadcasts, bosses, events and Big Boss's speech",
        5: "Radio: Big Boss, first set",
        6: "Radio: Big Boss, second set",
        7: "Radio: Schneider",
        8: "Radio: Diane and Steve",
        9: "Radio: Jennifer",
        13: "Radio: opening briefing",
        14: "Ending: Snake's report, news flash, staff credits and Big Boss",
        15: "Menus, item and weapon descriptions, boss names and records",
    },
    Game.MG2: {
        0: "Equipment names and descriptions",
        1: "Weapon names and descriptions",
        2: "Codec: Snake calling",
        3: "Codec: Campbell",
        4: "Codec: your number one fan and the pilot",
        5: "Codec: Holly",
        6: "Codec: Kasler",
        7: "Codec: Dr. Madnar",
        8: "Marv, who speaks Czech, and Gustava",
        9: "Codec: Master Miller",
        10: "Codec: Jacobsen",
        11: "Gray Fox",
        12: "Big Boss's final talk",
        13: "Gustava",
        14: "Guards and Snake during play",
        15: "Children",
        16: "Item pick-ups",
        17: "Opening story",
        18: "Staff credits",
        19: "Bosses and cut-scenes",
        20: "Escape and ending cut-scenes",
        21: "Debug warp-point names, never shown to players",
        22: "Codec contacts, pause and title menus, options",
        23: "Rank code names, boss names and results",
    },
}
_STYLES = {
    0: "dialogue, message or menu",
    1: "short exclamation",
    2: "item pick-up",
    3: "enemy broadcast",
    4: "radio message",
    5: "boss introduction or alarm",
    23: "notice",
    26: "event message",
}
_UI_BLOCKS = {Game.MG1: frozenset((15,)), Game.MG2: frozenset((21, 22, 23))}
# A line wider than the screen is one the game wraps, not a label.
_SCREEN_WIDTH = 512
# The European MG1 draws these strings of block 15 with the 8x8 sprite font of
# the HUD, which has the capitals and digits of ASCII and cells for B0 to DF.
_HUD_LABELS = frozenset((3, 4, 5, 6, 7, 8, 13, 14, 15, 141))
_HUD_BYTES = frozenset((*b" 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", *range(0xB0, 0xE0)))
# The shipped opening story and credits of MG2 have pages of more than ten
# lines, so a routine other than the message window lays them out.
_MG2_FREE_LAYOUT = frozenset((17, 18))
_MG2_PAGE_LINES = 10
_PAGE_BREAKS = frozenset(("{wait}", "{autowait}"))
# Double-byte characters and button icons advance as far as the font is high.
_WIDE_ADVANCE = 24
_PLACEHOLDER_NAME = re.compile(r"\{([a-z]+)")


def translator_notes(
    charset: Charset,
    page: Page,
    japanese: bool,
    block: int,
    number: int,
    data: bytes,
    style: int | None,
) -> tuple[str, ...]:
    """Return notes for translators on what the game does with a string.

    Args:
        charset: The characters of the text, with the game they belong to.
        page: Font page 0, whose glyphs give the width of the string.
        japanese: Whether the text is that of a Japanese release.
        block: The text block of the string.
        number: The position of the string in its block.
        data: The bytes of the string.
        style: The style byte of an MG1 string, None for MG2.
    """
    game = charset.game
    text = charset.decode(data)
    notes = [_DESCRIPTIONS[game][block]]
    if style is not None:
        meaning = _STYLES.get(style, "unknown")
        notes.append(f"Style {style} ({meaning}), kept in text.json")
    notes.append(f"The original takes {len(data)} bytes")
    width = _widest_line(charset, page, data)
    if _is_hud_label(game, japanese, block, number):
        notes.append(
            "Drawn with the 8x8 HUD font, 8 pixels a character: capitals, digits, "
            "and other letters at codes B0 to DF, whose cells are in images/62.000.png"
        )
    elif block in _UI_BLOCKS[game] and width <= _SCREEN_WIDTH:
        notes.append(f"Not wrapped, {width} pixels wide: keep it about as wide")
    else:
        wrapping = "Not wrapped" if japanese else "Wrapped at spaces"
        rules = [f"{wrapping}, at most {_line_bytes(game, japanese)} bytes a line"]
        if game is Game.MG1:
            rules.append("a blank line starts a page")
        elif block not in _MG2_FREE_LAYOUT:
            rules.append(
                f"at most {_MG2_PAGE_LINES} lines a page; {{wait}} and {{autowait}} start a page"
            )
        if japanese and game is Game.MG2:
            rules.append("{wait} hides the byte after it, so put a line break there")
        notes.append("; ".join(rules))
    used = set(_PLACEHOLDER_NAME.findall(text))
    notes += (PLACEHOLDERS[name] for name in PLACEHOLDERS if name in used)
    return tuple(notes)


def _widest_line(charset: Charset, page: Page, data: bytes) -> int:
    """Return the width in pixels of the widest line of a string."""
    widths = [0]
    for raw, _ in charset.characters(data):
        if raw == b"\n":
            widths.append(0)
        elif len(raw) == 2 and (raw[0] >= 0x80 or raw[0] == 0x7C):
            widths[-1] += _WIDE_ADVANCE
        elif len(raw) == 1 and (glyph := page.glyphs.get(raw[0])):
            widths[-1] += glyph.width
    return max(widths)


def _is_hud_label(game: Game, japanese: bool, block: int, number: int) -> bool:
    return game is Game.MG1 and not japanese and block == 15 and number in _HUD_LABELS


def _line_bytes(game: Game, japanese: bool) -> int:
    """Return how many bytes of text a line of the message window holds."""
    # Two of the 47 bytes of an MG2 line go to the indent of European lines.
    return 48 if game is Game.MG1 else 47 if japanese else 45


def display_problems(
    charset: Charset, font: Font, japanese: bool, block: int, number: int, data: bytes
) -> Iterator[str]:
    """Yield what keeps the game from showing a string as it is.

    Args:
        charset: The characters of the text, with the game they belong to.
        font: The font the game draws the text with.
        japanese: Whether the text is that of a Japanese release.
        block: The text block of the string.
        number: The position of the string in its block.
        data: The bytes of the string.
    """
    game = charset.game
    hud = _is_hud_label(game, japanese, block, number)
    glyphs = {glyph.code for glyph in font.double_byte}
    # Japanese lines are never wrapped, so each must fit whole.
    breaks = (b"\n",) if japanese else (b"\n", b" ")
    longest = run = 0
    lines = page_lines = 1
    previous = ""
    for raw, text in charset.characters(data):
        if japanese and previous == "{wait}":
            previous = text
            if raw not in (b"\n", b" "):
                yield (
                    "{wait} hides the byte after it, so follow it with a line break, "
                    f"not {text!r}"
                )
            continue
        previous = text
        if hud and not _HUD_BYTES.issuperset(raw):
            yield (
                f"{text!r} is not in the HUD font, which has capitals, digits and "
                "B0-DF (images/62.000.png)"
            )
        elif len(raw) == 2 and raw[0] >= 0x80 and int.from_bytes(raw) not in glyphs:
            yield (
                f"{text!r} has no glyph on font page 4: list it in the double_byte "
                "of font.json and draw its glyph"
            )
        elif len(raw) == 1 and raw[0] >= 0x20 and raw[0] not in font.pages[0].glyphs:
            yield (
                f"{text!r} ({raw[0]:02X}) has no glyph on font page 0: give it a "
                "width on page 0 of font.json and draw its glyph"
            )
        if raw == b"\\" and game is Game.MG2:
            yield "{x:5C} starts no engine code, which hangs the game"
        if text in _PAGE_BREAKS:
            run, page_lines = 0, 1
        elif raw in breaks:
            run = 0
            page_lines += raw == b"\n"
        else:
            run += len(raw)
        longest, lines = max(longest, run), max(lines, page_lines)
    if longest > (limit := _line_bytes(game, japanese)):
        what = "line" if japanese else "word"
        yield f"a {what} takes {longest} bytes, more than the {limit} of a line"
    if game is Game.MG2 and block not in _MG2_FREE_LAYOUT and lines > _MG2_PAGE_LINES:
        yield f"a page takes {lines} lines, more than the {_MG2_PAGE_LINES}"
