"""RIS export formatter — serializes ReferenceItems to .ris format."""

from __future__ import annotations

from typing import Any

from openscire.references.models import ReferenceItem

RIS_TYPE_MAP: dict[str, str] = {
    "journal_article": "JOUR",
    "book": "BOOK",
    "book_chapter": "CHAP",
    "conference_paper": "CONF",
    "thesis": "THES",
    "report": "RPRT",
    "patent": "PAT",
}

RIS_REVERSE_TYPE_MAP: dict[str, str] = {v: k for k, v in RIS_TYPE_MAP.items()}


def _format_ris_authors(authors: list[Any]) -> list[str]:
    """Format authors for RIS AU tags: 'Last, First'."""
    lines: list[str] = []
    for author in authors:
        if hasattr(author, "last") and author.last:
            first_part = getattr(author, "first", "")
            lines.append(f"AU  - {author.last}, {first_part}" if first_part else f"AU  - {author.last}")
        elif hasattr(author, "full") and author.full:
            lines.append(f"AU  - {author.full}")
    return lines


def _format_ris_keywords(keywords: list[str]) -> list[str]:
    return [f"KW  - {kw}" for kw in keywords]


def to_ris(references: list[ReferenceItem]) -> str:
    """Serialize a list of ReferenceItems to a RIS string."""
    records: list[str] = []

    for ref in references:
        lines: list[str] = []

        ris_type = RIS_TYPE_MAP.get(ref.item_type, "GEN")
        lines.append(f"TY  - {ris_type}")
        lines.append(f"ID  - {ref.id}")

        lines.extend(_format_ris_authors(ref.authors))

        if ref.title:
            lines.append(f"TI  - {ref.title}")
        if ref.journal:
            lines.append(f"JF  - {ref.journal}")
        if ref.doi:
            lines.append(f"DO  - {ref.doi}")
        if ref.year is not None:
            lines.append(f"PY  - {ref.year}")
        if ref.volume:
            lines.append(f"VL  - {ref.volume}")
        if ref.issue:
            lines.append(f"IS  - {ref.issue}")
        if ref.pages:
            pages = ref.pages
            if "-" in pages:
                sp, _, ep = pages.partition("-")
                lines.append(f"SP  - {sp.strip()}")
                lines.append(f"EP  - {ep.strip()}")
            else:
                lines.append(f"SP  - {pages}")
        if ref.publisher:
            lines.append(f"PB  - {ref.publisher}")
        if ref.abstract:
            lines.append(f"N2  - {ref.abstract}")
        if ref.url:
            lines.append(f"UR  - {ref.url}")
        lines.extend(_format_ris_keywords(ref.keywords))

        lines.append("ER  -")
        records.append("\n".join(lines))

    return "\n\n".join(records) + "\n"
