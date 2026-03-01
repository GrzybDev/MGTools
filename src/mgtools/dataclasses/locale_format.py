from enum import Enum


class LocaleFormat(str, Enum):
    XLIFF = "xliff"
    XLF = "xliff2"
    PO = "po"
