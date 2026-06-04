# SPDX-License-Identifier: Apache-2.0

"""CSL-JSON file format importer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openscire.references.importers.base import ReferenceImporter
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource

CSL_TYPE_MAP: dict[str, str] = {
    "article-journal": "journal_article",
    "book": "book",
    "chapter": "book_chapter",
    "paper-conference": "conference_paper",
    "thesis": "thesis",
    "report": "report",
    "patent": "patent",
    "article": "journal_article",
}


def _parse_csl_author(author: dict[str, Any]) -> ReferenceAuthor:
    return ReferenceAuthor(
        first=author.get("given", ""),
        last=author.get("family", ""),
        full=author.get("literal", ""),
    )


class CslJsonImporter(ReferenceImporter):
    """Parse CSL-JSON content into ReferenceItems."""

    def parse(self, content: str | bytes) -> list[ReferenceItem]:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        data: list[dict[str, Any]] | dict[str, Any] = json.loads(content)
        if isinstance(data, dict):
            data = [data]
        return [self._parse_item(item) for item in data]

    def parse_file(self, path: str | Path) -> list[ReferenceItem]:
        path = Path(path)
        return self.parse(path.read_text(encoding="utf-8"))

    @staticmethod
    def _parse_item(item: dict[str, Any]) -> ReferenceItem:
        doi = item.get("DOI", "")
        title = item.get("title", "")
        csl_type = item.get("type", "")
        year = None
        issued = item.get("issued", {})
        if isinstance(issued, dict):
            date_parts = issued.get("date-parts")
            if date_parts and len(date_parts) > 0 and len(date_parts[0]) > 0:
                year = int(date_parts[0][0])

        authors = [_parse_csl_author(a) for a in item.get("author", [])]

        keywords = [k.strip() for k in item.get("keyword", "").split(",") if k.strip()]

        return ReferenceItem(
            id=item.get("id", "") or doi or title[:50],
            source=ReferenceSource.csl_json,
            doi=doi,
            title=title,
            authors=authors,
            journal=item.get("container-title", ""),
            year=year,
            volume=item.get("volume", ""),
            issue=item.get("issue", ""),
            pages=item.get("page", ""),
            publisher=item.get("publisher", ""),
            abstract=item.get("abstract", ""),
            keywords=keywords,
            url=item.get("URL", ""),
            item_type=CSL_TYPE_MAP.get(csl_type, csl_type),
            extra=item,
        )
