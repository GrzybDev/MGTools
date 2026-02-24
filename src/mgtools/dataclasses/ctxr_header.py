from dataclasses import dataclass, field


@dataclass
class CtxrHeader:
    padding: int = 0
    version: int = 7
    width: int = 0
    height: int = 0
    unknown_0c: int = 1
    unknown_0e: int = 0
    unknown_10: int = 0
    color_0: bytes = field(default_factory=lambda: b"\x00\x00\x00\xff")
    color_1: bytes = field(default_factory=lambda: b"\x00\x00\x00\x00")
    color_2: bytes = field(default_factory=lambda: b"\x00\x00\x00\x00")
    color_3: bytes = field(default_factory=lambda: b"\xff\x00\x00\x00")
    unknown_24: int = 0
    reserved: bytes = field(default_factory=lambda: b"\x00" * 88)
