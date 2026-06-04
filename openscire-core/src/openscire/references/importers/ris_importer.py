# SPDX-License-Identifier: Apache-2.0

"""RIS file format importer (tagged line format, stdlib only)."""

from __future__ import annotations

import re
from pathlib import Path

from openscire.references.importers.base import ReferenceImporter
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource

TYPE_MAP: dict[str, str] = {
    "JOUR": "journal_article",
    "BOOK": "book",
    "CHAP": "book_chapter",
    "CONF": "conference_paper",
    "THES": "thesis",
    "RPRT": "report",
    "PAT": "patent",
    "GEN": "generic",
}


def _parse_ris_date(date_str: str) -> int | None:
    """Extract year from RIS date field (e.g. '2024/01/15' or '2024')."""
    m = re.match(r"(\d{4})", date_str.strip())
    return int(m.group(1)) if m else None


class RisImporter(ReferenceImporter):
    """Parse RIS content into ReferenceItems."""

    def parse(self, content: str | bytes) -> list[ReferenceItem]:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        records = self._split_records(content)
        return [self._parse_record(r) for r in records if r.strip()]

    def parse_file(self, path: str | Path) -> list[ReferenceItem]:
        path = Path(path)
        return self.parse(path.read_bytes())

    @staticmethod
    def _split_records(content: str) -> list[str]:
        """Split RIS content into individual records (separated by ER  -)."""
        return re.split(r"\nER\s*-\s*\n?", content.strip())

    @staticmethod
    def _parse_record(text: str) -> ReferenceItem:  # noqa: PLR0912
        fields: dict[str, list[str]] = {}
        for line in text.splitlines():
            line = line.strip()
            if len(line) < 5 or line[4] != "-":
                continue
            tag = line[:2].strip()
            value = line[6:].strip()
            fields.setdefault(tag, []).append(value)

        authors: list[ReferenceAuthor] = []
        for au in fields.get("AU", []):
            if "," in au:
                last, first = au.split(",", 1)
                authors.append(ReferenceAuthor(first=first.strip(), last=last.strip()))
            else:
                authors.append(ReferenceAuthor(full=au.strip()))

        for au in fields.get("A1", []):
            if "," in au:
                last, first = au.split(",", 1)
                authors.append(ReferenceAuthor(first=first.strip(), last=last.strip()))
            else:
                authors.append(ReferenceAuthor(full=au.strip()))

        keywords = [k.strip() for k in fields.get("KW", []) if k.strip()]

        ty = fields.get("TY", ["GEN"])[0]
        doi = fields.get("DO", [""])[0] or fields.get("M1", [""])[0] or fields.get("M3", [""])[0]
        title = fields.get("T1", [""])[0] or fields.get("TI", [""])[0]
        journal = fields.get("JF", [""])[0] or fields.get("JO", [""])[0]
        year = _parse_ris_date(fields.get("Y1", [""])[0] or fields.get("PY", [""])[0])
        volume = fields.get("VL", [""])[0]
        issue = fields.get("IS", [""])[0]
        pages = fields.get("SP", [""])[0]
        if pages and fields.get("EP", [""]):
            pages = f"{pages}-{fields['EP'][0]}"
        publisher = fields.get("PB", [""])[0]
        abstract = fields.get("N2", [""])[0] or fields.get("AB", [""])[0]
        url = fields.get("UR", [""])[0]

        return ReferenceItem(
            id=fields.get("ID", [""])[0] or doi or title[:50],
            source=ReferenceSource.ris,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            volume=volume,
            issue=issue,
            pages=pages,
            publisher=publisher,
            abstract=abstract,
            keywords=keywords,
            url=url,
            item_type=TYPE_MAP.get(ty, "generic"),
            extra={"ris_type": ty, "raw_tags": fields},
        )
