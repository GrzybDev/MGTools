from abc import ABC, abstractmethod
from pathlib import Path


class File(ABC):

    @abstractmethod
    def save(self, path: Path) -> None:
        raise NotImplementedError("Subclasses must implement save method")
