# SPDX-License-Identifier: Apache-2.0

"""BibTeX file format importer using brace-depth parsing (stdlib only)."""

from __future__ import annotations

import re
from pathlib import Path

from openscire.references.importers.base import ReferenceImporter
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


def _find_matching_brace(text: str, start: int) -> int:
    """Find the index of the matching closing brace from ``start`` (which should point to ``{``).

    Returns the index of the matching ``}``, or -1 if not found.
    """
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _extract_braced(text: str, start: int) -> tuple[str, int] | None:
    """Extract the braced value starting at ``start`` (which should point to ``{``).

    Returns (content_without_outer_braces, end_index) or None.
    """
    end = _find_matching_brace(text, start)
    if end == -1:
        return None
    return (text[start + 1 : end], end)


def _strip_braces(value: str) -> str:
    """Remove outer braces and collapse whitespace."""
    value = value.strip()
    while value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        if "{" in inner or "}" in inner:
            break
        value = inner
    return re.sub(r"\s+", " ", value).strip()


def _parse_authors(author_field: str) -> list[ReferenceAuthor]:
    """Parse BibTeX author field: 'Last, First and Last, First'."""
    authors: list[ReferenceAuthor] = []
    for part in re.split(r"\s+and\s+", author_field):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            last, first = part.split(",", 1)
            authors.append(ReferenceAuthor(first=_strip_braces(first), last=_strip_braces(last)))
        else:
            authors.append(ReferenceAuthor(full=_strip_braces(part)))
    return authors


def _split_entries(content: str) -> list[tuple[str, str, str]]:
    """Split BibTeX content into (type, citekey, body) tuples.

    Uses brace-depth tracking instead of regex to handle nested braces.
    """
    entries: list[tuple[str, str, str]] = []
    i = 0
    while i < len(content):
        at = content.find("@", i)
        if at == -1:
            break
        i = at + 1
        # Extract entry type
        m = re.match(r"(\w+)", content[i:])
        if not m:
            continue
        entry_type = m.group(1).lower()
        i += m.end()
        # Skip whitespace and find opening brace
        while i < len(content) and content[i] in " \t\n\r":
            i += 1
        if i >= len(content) or content[i] != "{":
            continue
        # Extract body (with nested brace tracking)
        body_end = _find_matching_brace(content, i)
        if body_end == -1:
            continue
        body = content[i + 1 : body_end]
        i = body_end + 1
        # Parse cite key (first token before comma or newline)
        citekey = ""
        for j, ch in enumerate(body):
            if ch in ",\n\r\t ":
                citekey = body[:j].strip()
                body = body[j:]
                break
        entries.append((entry_type, citekey.strip(), body.strip()))
    return entries


def _parse_fields(body: str) -> dict[str, str]:
    """Parse key = {value} fields from BibTeX entry body with brace-depth tracking."""
    fields: dict[str, str] = {}
    i = 0
    while i < len(body):
        # Skip non-alphanumeric
        if not body[i].isalpha() and body[i] != "_":
            i += 1
            continue
        # Try to match a field
        m = re.match(r"(\w+)\s*=\s*", body[i:])
        if not m:
            i += 1
            continue
        key = m.group(1).lower()
        i += m.end()
        # Skip whitespace
        while i < len(body) and body[i] in " \t\n\r":
            i += 1
        if i >= len(body):
            break
        # Extract value
        if body[i] == "{":
            result = _extract_braced(body, i)
            if result is None:
                i += 1
                continue
            value, end = result
            fields[key] = _strip_braces(value)
            i = end + 1
        elif body[i] == '"':
            end = body.find('"', i + 1)
            if end == -1:
                break
            fields[key] = body[i + 1 : end]
            i = end + 1
        else:
            # Unbraced value (number, etc.) — read until comma or end
            end = i
            while end < len(body) and body[end] not in ",}\n\r":
                end += 1
            fields[key] = body[i:end].strip()
            i = end
        # Skip trailing comma and whitespace
        while i < len(body) and body[i] in ", \t\n\r":
            i += 1
    return fields


class BibtexImporter(ReferenceImporter):
    """Parse BibTeX content into ReferenceItems."""

    def parse(self, content: str | bytes) -> list[ReferenceItem]:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        items: list[ReferenceItem] = []
        for entry_type, citekey, body in _split_entries(content):
            item = self._parse_entry(entry_type, citekey, body)
            if item is not None:
                items.append(item)
        return items

    def parse_file(self, path: str | Path) -> list[ReferenceItem]:
        path = Path(path)
        return self.parse(path.read_text(encoding="utf-8"))

    @staticmethod
    def _parse_entry(entry_type: str, citekey: str, body: str) -> ReferenceItem | None:  # noqa: PLR0912
        fields = _parse_fields(body)

        authors = _parse_authors(fields.get("author", ""))
        doi = fields.get("doi", "")
        title = fields.get("title", "")
        year_str = fields.get("year", "")
        year = int(year_str) if year_str and year_str.isdigit() else None

        return ReferenceItem(
            id=citekey,
            source=ReferenceSource.bibtex,
            doi=doi,
            title=title,
            authors=authors,
            journal=fields.get("journal", ""),
            year=year,
            volume=fields.get("volume", ""),
            issue=fields.get("number", ""),
            pages=fields.get("pages", ""),
            publisher=fields.get("publisher", ""),
            abstract=fields.get("abstract", ""),
            keywords=[k.strip() for k in fields.get("keywords", "").split(",") if k.strip()],
            url=fields.get("url", ""),
            item_type=entry_type,
            extra=fields,
        )
