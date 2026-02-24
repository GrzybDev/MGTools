from dataclasses import dataclass


@dataclass
class CtxrMipLevel:
    width: int
    height: int
    data: bytes
