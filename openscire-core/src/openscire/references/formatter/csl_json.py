"""CSL-JSON export formatter — serializes ReferenceItems to CSL-JSON format."""

from __future__ import annotations

import json
from typing import Any

from openscire.references.models import ReferenceItem

CSL_TYPE_MAP_REVERSE: dict[str, str] = {
    "journal_article": "article-journal",
    "book": "book",
    "book_chapter": "chapter",
    "conference_paper": "paper-conference",
    "thesis": "thesis",
    "report": "report",
    "patent": "patent",
}


def _format_csl_author(author: Any) -> dict[str, str]:
    """Format a ReferenceAuthor into a CSL-JSON author object."""
    result: dict[str, str] = {}
    if hasattr(author, "last") and author.last:
        result["family"] = author.last
    if hasattr(author, "first") and author.first:
        result["given"] = author.first
    if hasattr(author, "full") and author.full:
        result["literal"] = author.full
    return result


def _ref_to_csl_item(ref: ReferenceItem) -> dict[str, Any]:
    """Convert a single ReferenceItem to a CSL-JSON citation dict."""
    csl_type = CSL_TYPE_MAP_REVERSE.get(ref.item_type, "article")

    item: dict[str, Any] = {
        "id": ref.id,
        "type": csl_type,
    }

    if ref.title:
        item["title"] = ref.title
    if ref.doi:
        item["DOI"] = ref.doi
    if ref.authors:
        item["author"] = [_format_csl_author(a) for a in ref.authors]
    if ref.journal:
        item["container-title"] = ref.journal
    if ref.volume:
        item["volume"] = ref.volume
    if ref.issue:
        item["issue"] = ref.issue
    if ref.pages:
        item["page"] = ref.pages
    if ref.publisher:
        item["publisher"] = ref.publisher
    if ref.abstract:
        item["abstract"] = ref.abstract
    if ref.url:
        item["URL"] = ref.url
    if ref.keywords:
        item["keyword"] = ", ".join(ref.keywords)
    if ref.year is not None:
        item["issued"] = {"date-parts": [[ref.year]]}

    return item


def to_csl_json(references: list[ReferenceItem], indent: int | None = 2) -> str:
    """Serialize a list of ReferenceItems to a CSL-JSON string."""
    items = [_ref_to_csl_item(r) for r in references]
    return json.dumps(items, indent=indent, ensure_ascii=False) + "\n"
