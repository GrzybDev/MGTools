from mgtools.enumerators.file_type import FileType

DATA_TYPE_MAP = {}

# Palette configuration for MG2 sprite sections.
# Section 24 uses two large blocks: block 39 at index 0 (covers 0-90)
# and block 37 at index 96 (covers 96-206).
MG2_PALETTE_SECTION_24_BLOCKS: list[tuple[int, int]] = [(39, 0), (37, 96)]

# Sections 25-45 each use a single palette block whose colours start at
# this offset within the 256-entry palette.
MG2_PALETTE_SPRITE_OFFSET: int = 192

FILE_TYPE_MAP = {
    2: FileType.LOCALE,
    24: FileType.SPRITE,
    25: FileType.SPRITE,
    26: FileType.SPRITE,
    27: FileType.SPRITE,
    28: FileType.SPRITE,
    29: FileType.SPRITE,
    30: FileType.SPRITE,
    31: FileType.SPRITE,
    32: FileType.SPRITE,
    33: FileType.SPRITE,
    34: FileType.SPRITE,
    35: FileType.SPRITE,
    36: FileType.SPRITE,
    37: FileType.SPRITE,
    38: FileType.SPRITE,
    39: FileType.SPRITE,
    40: FileType.SPRITE,
    41: FileType.SPRITE,
    42: FileType.SPRITE,
    43: FileType.SPRITE,
    44: FileType.SPRITE,
    45: FileType.SPRITE,
    46: FileType.PALETTE,
    47: FileType.TEXTURE,
    48: FileType.FONT,
}
