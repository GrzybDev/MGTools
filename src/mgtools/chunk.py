from abc import ABC, abstractmethod
from io import BytesIO


class Chunk(ABC):

    @property
    @abstractmethod
    def data(self) -> BytesIO:
        raise NotImplementedError("Subclasses must implement data property")
