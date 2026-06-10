# SPDX-License-Identifier: Apache-2.0

"""Abstract base class for reference file format importers."""

from abc import ABC, abstractmethod
from pathlib import Path

from openscire.references.models import ReferenceItem


class ReferenceImporter(ABC):
    """Parse reference metadata from a file format into ReferenceItems."""

    @abstractmethod
    def parse(self, content: str | bytes) -> list[ReferenceItem]: ...

    def parse_file(self, path: str | Path) -> list[ReferenceItem]:
        path = Path(path)
        raw = path.read_bytes() if path.suffix == ".ris" else path.read_text(encoding="utf-8")
        return self.parse(raw)
