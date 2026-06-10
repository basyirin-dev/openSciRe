"""BibTeX export formatter — serializes ReferenceItems to .bib format."""

from __future__ import annotations

from typing import Any

from openscire.references.models import ReferenceItem

BIBTEX_TYPE_MAP: dict[str, str] = {
    "journal_article": "article",
    "book": "book",
    "book_chapter": "inbook",
    "conference_paper": "inproceedings",
    "thesis": "phdthesis",
    "report": "techreport",
    "patent": "patent",
    "generic": "misc",
}


def _escape_bibtex(text: str) -> str:
    """Escape special BibTeX characters."""
    chars = {
        "\\": "\\\\",
        "{": "\\{",
        "}": "\\}",
        "$": "\\$",
        "&": "\\&",
        "#": "\\#",
        "_": "\\_",
        "%": "\\%",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
    }
    result = []
    for ch in text:
        if ch in chars:
            result.append(chars[ch])
        else:
            result.append(ch)
    return "".join(result)


def _format_bibtex_authors(authors: list[Any]) -> str:
    """Format authors as 'Last, First and Last, First'."""
    parts: list[str] = []
    for author in authors:
        if hasattr(author, "last") and author.last:
            first_part = getattr(author, "first", "")
            parts.append(f"{author.last}, {first_part}" if first_part else author.last)
        elif hasattr(author, "full") and author.full:
            parts.append(author.full)
        else:
            parts.append(str(author))
    return " and ".join(parts)


def _generate_citekey(ref: ReferenceItem) -> str:
    """Generate a unique cite key from first author last name + year + first keyword."""
    surname = ""
    if ref.authors and hasattr(ref.authors[0], "last") and ref.authors[0].last:
        surname = ref.authors[0].last
    elif ref.authors and hasattr(ref.authors[0], "full") and ref.authors[0].full:
        surname = ref.authors[0].full.split()[-1]

    year_str = str(ref.year) if ref.year is not None else "n.d."

    keyword = ""
    if ref.keywords:
        keyword = ref.keywords[0]

    key = f"{surname}{year_str}{keyword}"
    # Strip non-alphanumeric except underscore
    key = "".join(c for c in key if c.isalnum() or c == "_")
    return key if key else f"ref{hash(ref.id) % 10000}"


def to_bibtex(references: list[ReferenceItem]) -> str:
    """Serialize a list of ReferenceItems to a BibTeX string."""
    entries: list[str] = []

    for ref in references:
        bib_type = BIBTEX_TYPE_MAP.get(ref.item_type, "misc")
        citekey = _generate_citekey(ref)

        fields: dict[str, str] = {}

        if ref.authors:
            fields["author"] = _format_bibtex_authors(ref.authors)
        if ref.title:
            fields["title"] = _escape_bibtex(ref.title)
        if ref.journal:
            fields["journal"] = _escape_bibtex(ref.journal)
        if ref.year is not None:
            fields["year"] = str(ref.year)
        if ref.volume:
            fields["volume"] = ref.volume
        if ref.issue:
            fields["number"] = ref.issue
        if ref.pages:
            fields["pages"] = ref.pages
        if ref.publisher:
            fields["publisher"] = _escape_bibtex(ref.publisher)
        if ref.doi:
            fields["doi"] = ref.doi
        if ref.url:
            fields["url"] = ref.url
        if ref.abstract:
            fields["abstract"] = _escape_bibtex(ref.abstract)
        if ref.keywords:
            fields["keywords"] = ", ".join(ref.keywords)

        field_lines = "\n".join(f"  {key} = {{{value}}}," for key, value in fields.items())

        entry = f"@{bib_type}{{{citekey},\n{field_lines}\n}}"
        entries.append(entry)

    return "\n\n".join(entries) + "\n"
