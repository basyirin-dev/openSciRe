# SPDX-License-Identifier: Apache-2.0

"""Endnote XML file format importer (stdlib xml.etree)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from openscire.references.importers.base import ReferenceImporter
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource

REF_TYPE_MAP: dict[str, str] = {
    "0": "journal_article",
    "1": "book",
    "2": "book_chapter",
    "3": "conference_paper",
    "6": "report",
    "7": "thesis",
    "8": "patent",
}


class EndnoteImporter(ReferenceImporter):
    """Parse Endnote XML content into ReferenceItems."""

    def parse(self, content: str | bytes) -> list[ReferenceItem]:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        root = ET.fromstring(content)
        items: list[ReferenceItem] = []
        for record in root.findall(".//record"):
            item = self._parse_record(record)
            if item is not None:
                items.append(item)
        return items

    def parse_file(self, path: str | Path) -> list[ReferenceItem]:
        path = Path(path)
        return self.parse(path.read_bytes())

    @staticmethod
    def _parse_record(record: ET.Element) -> ReferenceItem | None:  # noqa: PLR0912
        def _text(tag: str) -> str:
            el = record.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        def _texts(tag: str) -> list[str]:
            return [el.text.strip() for el in record.findall(tag) if el.text]

        ref_type = _text("ref-type")
        authors: list[ReferenceAuthor] = []
        for author_el in record.findall("contributors/authors/author"):
            first = _text_in_el(author_el, "first") if author_el is not None else ""
            last = _text_in_el(author_el, "last") if author_el is not None else ""
            if first or last:
                authors.append(ReferenceAuthor(first=first, last=last))
            else:
                full = author_el.text.strip() if author_el is not None and author_el.text else ""
                if full:
                    authors.append(ReferenceAuthor(full=full))

        year_str = _text("dates/year")
        year = int(year_str) if year_str and year_str.isdigit() else None

        doi = _text("electronic-resource-num")
        if not doi:
            doi = _text("accession-num")

        keywords = [k.strip() for k in _texts("keywords/keyword") if k.strip()]

        pages = _text("pages")
        if pages and " " in pages:
            pages = pages.replace(" ", "")

        return ReferenceItem(
            id=_text("rec-number") or doi or "",
            source=ReferenceSource.endnote_xml,
            doi=doi,
            title=_text("titles/title"),
            authors=authors,
            journal=_text("periodical/abbr1") or _text("periodical/full-title"),
            year=year,
            volume=_text("volume"),
            issue=_text("number"),
            pages=pages,
            publisher=_text("publisher"),
            abstract=_text("abstract"),
            keywords=keywords,
            url=_text("urls/web-url"),
            item_type=REF_TYPE_MAP.get(ref_type, "generic"),
            extra={"ref_type": ref_type},
        )


def _text_in_el(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag)
    return el.text.strip() if el is not None and el.text else ""
