from mgtools.mg1.enumerators.file_type import FileType

FILE_TYPE_MAP = {
    41: FileType.SPRITE,
    42: FileType.SPRITE,
    43: FileType.SPRITE,
    44: FileType.SPRITE,
    45: FileType.SPRITE,
    46: FileType.SPRITE,
    47: FileType.SPRITE,
    48: FileType.SPRITE,
    49: FileType.SPRITE,
    50: FileType.SPRITE,
    51: FileType.SPRITE,
    53: FileType.SPRITE,
    54: FileType.SPRITE,
    55: FileType.SPRITE,
    56: FileType.SPRITE,
    57: FileType.SPRITE,
    58: FileType.SPRITE,
    59: FileType.SPRITE,
    60: FileType.SPRITE,
    61: FileType.SPRITE,
    62: FileType.SPRITE,
    63: FileType.SPRITE,
    64: FileType.SPRITE,
    65: FileType.SPRITE,
    66: FileType.SPRITE,
    67: FileType.SPRITE,
    68: FileType.SPRITE,
    69: FileType.SPRITE,
    70: FileType.SPRITE,
    72: FileType.LOCALE,
    74: FileType.PALETTE,
    75: FileType.FONT,
}

FILE_NAME_MAP = {
    41: "ui",
    62: "font_additional_chars",
    69: "vs",
    70: "character_names",
    74: "palette",
}

LOCALIZABLE_CHUNKS = [41, 62, 69, 70, 72, 74, 75]
TEXT_BLOCKS = [3, 4, 5, 6, 7, 8, 9, 13, 14, 15]
TEXT_BLOCKS_NAMES = {
    3: "miscellaneous_1",
    4: "miscellaneous_2",
    5: "radio_big_boss_1",
    6: "radio_big_boss_2",
    7: "radio_resistance_leader",
    8: "radio_steve_diane",
    9: "radio_jennifer",
    13: "opening",
    14: "ending",
    15: "frontend",
}
