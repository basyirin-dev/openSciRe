# SPDX-License-Identifier: Apache-2.0

"""MEDLINE tagged format importer (NLM style, stdlib only)."""

from __future__ import annotations

import re
from pathlib import Path

from openscire.references.importers.base import ReferenceImporter
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource

FIELD_MAP: dict[str, str] = {
    "PMID": "pmid",
    "TI": "title",
    "AB": "abstract",
    "AD": "affiliation",
    "LA": "language",
    "TA": "journal",
    "JT": "journal_full",
    "VI": "volume",
    "IP": "issue",
    "PG": "pages",
    "DP": "date_publication",
    "SO": "source",
    "PT": "publication_type",
    "DEP": "date_electronic",
    "PL": "place",
    "SB": "subset",
    "CY": "country",
    "OWN": "owner",
    "STAT": "status",
    "DA": "date_created",
    "LR": "date_revised",
    "IS": "issn",
}


def _parse_year(dp: str) -> int | None:
    """Extract year from DP (Date of Publication) field.

    Formats: '2024', '2024 Jan', '2024 Jan-Jun', '2024 Jan 15'
    """
    m = re.match(r"(\d{4})", dp.strip())
    return int(m.group(1)) if m else None


def _parse_authors(au_lines: list[str]) -> list[ReferenceAuthor]:
    """Parse MEDLINE author lines: 'LastName FM' or 'LastName FM, suffix'."""
    authors: list[ReferenceAuthor] = []
    for line in au_lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
        last = parts[0].rstrip(",")
        first = " ".join(parts[1:]).strip().rstrip(",")
        authors.append(ReferenceAuthor(first=first, last=last))
    return authors


def _find_doi(aid_lines: list[str]) -> str:
    """Extract DOI from AID field lines marked with [doi]."""
    for line in aid_lines:
        if "[doi]" in line:
            return line.split("[doi]")[0].strip()
    return ""


class MedlineImporter(ReferenceImporter):
    """Parse MEDLINE/NLM tagged format into ReferenceItems.

    MEDLINE records use two-character tags followed by '- '.
    Records are separated by 'PMID- ' lines or blank lines.
    """

    def parse(self, content: str | bytes) -> list[ReferenceItem]:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        records = self._split_records(content)
        return [self._parse_record(r) for r in records if r.strip()]

    def parse_file(self, path: str | Path) -> list[ReferenceItem]:
        path = Path(path)
        if path.suffix == ".medline":
            return self.parse(path.read_bytes())
        return self.parse(path.read_text(encoding="utf-8"))

    @staticmethod
    def _split_records(content: str) -> list[str]:
        """Split MEDLINE content into individual records on PMID- boundaries."""
        parts = re.split(r"\nPMID- ", content)
        records: list[str] = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if not p.startswith("PMID- ") and len(records) == 0:
                records.append(p)
            else:
                idx = p.index("PMID- ") if "PMID- " in p else -1
                if idx >= 0:
                    p = p[idx + 6:]
                records.append(p)
        return records

    @staticmethod
    def _parse_record(text: str) -> ReferenceItem:  # noqa: PLR0912
        fields: dict[str, list[str]] = {}
        current_tag = ""
        lines = text.splitlines()
        for i, line in enumerate(lines):
            line = line.rstrip()
            # Handle bare PMID on first line (stripped by _split_records)
            if i == 0 and line and line[0].isdigit():
                fields.setdefault("PMID", []).append(line.strip())
                continue
            # MEDLINE/NLM tagged line: tag space-padded to 4 chars + "- " + value
            # e.g. "TI  - title", "PMID- 12345", "MH  - Term/qualifier"
            if len(line) >= 6 and line[4:6] == "- ":
                tag = line[:4].strip()
                value = line[6:].strip()
                current_tag = tag
                fields.setdefault(tag, []).append(value)
            elif current_tag and line.startswith("      "):
                fields.setdefault(current_tag, [])
                if fields[current_tag]:
                    fields[current_tag][-1] += " " + line.strip()
                else:
                    fields[current_tag].append(line.strip())

        pmid = fields.get("PMID", [""])[0]
        title = fields.get("TI", [""])[0]
        if title.startswith(" "):
            title = title.strip()
        abstract = fields.get("AB", [""])[0]

        authors = _parse_authors(fields.get("AU", []))

        doi = _find_doi(fields.get("AID", []))

        ta = fields.get("TA", [""])[0]
        jt = fields.get("JT", [""])[0]
        journal = ta or jt

        year = _parse_year(fields.get("DP", [""])[0])

        volume = fields.get("VI", [""])[0]
        issue = fields.get("IP", [""])[0]
        pages = fields.get("PG", [""])[0]

        mesh_terms = fields.get("MH", [])
        pub_types = fields.get("PT", [])
        language = fields.get("LA", [""])[0]
        affiliation = fields.get("AD", [""])[0]

        extra: dict[str, object] = {}
        if mesh_terms:
            extra["mesh_terms"] = mesh_terms
        if pub_types:
            extra["publication_types"] = pub_types
        if language:
            extra["language"] = language
        if affiliation:
            extra["affiliation"] = affiliation
        if pmid:
            extra["pmid"] = pmid

        keywords = [m.split("/")[0].strip() for m in mesh_terms]

        return ReferenceItem(
            id=pmid or "",
            source=ReferenceSource.pubmed,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            volume=volume,
            issue=issue,
            pages=pages,
            abstract=abstract,
            keywords=keywords,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            item_type="journal_article",
            extra=extra,
        )
