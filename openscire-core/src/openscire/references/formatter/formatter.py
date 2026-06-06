"""CitationFormatter — style-aware inline and reference list formatting."""

from __future__ import annotations

import re
from typing import Any

from openscire.references.formatter.models import (
    AuthorFormat,
    CitationStyle,
    FormattedCitation,
    FormattedReference,
    InlineFormat,
    ReferenceOrder,
    StyleConfig,
)
from openscire.references.formatter.styles import BUILT_IN_STYLES
from openscire.references.models import ReferenceAuthor, ReferenceItem


def _format_authors(
    authors: list[ReferenceAuthor],
    author_format: AuthorFormat,
    et_al_threshold: int,
    max_authors: int,
    use_ampersand: bool,
) -> str:
    """Format author list per style configuration."""
    if not authors:
        return ""

    threshold = min(et_al_threshold, max_authors)
    display_authors = authors[:threshold]
    has_overflow = len(authors) > threshold

    formatted: list[str] = []
    for author in display_authors:
        if author_format == AuthorFormat.LAST_FIRST:
            first_init = author.first[0] + "." if author.first else ""
            formatted.append(f"{author.last}, {first_init}" if first_init else author.last)
        elif author_format == AuthorFormat.FIRST_LAST:
            first_init = author.first[0] + "." if author.first else ""
            formatted.append(f"{first_init} {author.last}" if first_init else author.last)
        elif author_format == AuthorFormat.LAST_FIRST_FULL:
            formatted.append(f"{author.last}, {author.first}" if author.first else author.last)
        elif author_format == AuthorFormat.FULL:
            formatted.append(author.full or f"{author.first} {author.last}".strip())

    if has_overflow:
        formatted.append("et al.")

    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        if use_ampersand:
            return ", & ".join(formatted)
        return " and ".join(formatted)
    last = formatted.pop()
    joiner = " & " if use_ampersand else " and "
    return ", ".join(formatted) + joiner + last


class CitationFormatter:
    """Format citations and reference lists per style configuration."""

    def __init__(
        self,
        style: CitationStyle | str = CitationStyle.APA,
        custom_config: StyleConfig | None = None,
    ) -> None:
        if isinstance(style, str):
            try:
                resolved = CitationStyle(style)
            except ValueError:
                resolved = CitationStyle.APA
        else:
            resolved = style

        base = BUILT_IN_STYLES.get(resolved)
        if custom_config is not None:
            self.config = custom_config
        elif base is not None:
            self.config = base
        else:
            self.config = BUILT_IN_STYLES[CitationStyle.APA]

        self._style = resolved

    @property
    def style(self) -> CitationStyle:
        return self._style

    def format_inline(
        self,
        reference: ReferenceItem,
        number: int | None = None,
    ) -> FormattedCitation:
        authors_str = _format_authors(
            reference.authors,
            self.config.author_format,
            self.config.et_al_threshold,
            self.config.max_authors,
            self.config.use_ampersand,
        )
        year = str(reference.year) if reference.year is not None else "n.d."
        style = self.config.name

        if self.config.inline_format == InlineFormat.AUTHOR_YEAR_PAREN:
            if authors_str:
                text = f"({authors_str}, {year})"
            else:
                text = f"({year})"

        elif self.config.inline_format == InlineFormat.AUTHOR_YEAR_NOPAREN:
            if authors_str:
                text = f"{authors_str} ({year})"
            else:
                text = f"({year})"

        elif self.config.inline_format == InlineFormat.NUMERIC_BRACKET:
            num = number if number is not None else 1
            text = f"[{num}]"

        elif self.config.inline_format == InlineFormat.NUMERIC_SUPERSCRIPT:
            num = number if number is not None else 1
            text = f"\u207b¹\u00b9"  # fallback: use [num] for plain text
            text = f"[{num}]"

        elif self.config.inline_format == InlineFormat.AUTHOR_NUMERIC:
            num = number if number is not None else 1
            if authors_str:
                text = f"{authors_str} [{num}]"
            else:
                text = f"[{num}]"

        else:
            text = f"[{reference.id}]"

        return FormattedCitation(
            text=text,
            reference_number=number,
            style=style,
        )

    def _resolve_doi(self, doi: str) -> str:
        if not doi:
            return ""
        return self.config.doi_prefix + doi

    def _fill_template(self, ref: ReferenceItem, number: int) -> str:
        template = self.config.format_template
        if not template:
            return f"[{ref.id}]"

        authors_str = _format_authors(
            ref.authors,
            self.config.author_format,
            self.config.et_al_threshold,
            self.config.max_authors,
            self.config.use_ampersand,
        )

        doi_str = self._resolve_doi(ref.doi) if ref.doi else ""

        replacements: dict[str, str] = {
            "{number}": str(number),
            "{authors}": authors_str,
            "{title}": ref.title,
            "{journal}": ref.journal,
            "{year}": str(ref.year) if ref.year is not None else "n.d.",
            "{volume}": ref.volume,
            "{issue}": ref.issue,
            "{pages}": ref.pages,
            "{doi}": doi_str,
            "{publisher}": ref.publisher,
            "{url}": ref.url,
            "{type}": ref.item_type,
        }

        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        # Clean up empty fields: remove "(issue)" when no issue, ", pages" when no pages, etc.
        result = re.sub(r"\s*\(\)", "", result)
        result = re.sub(r"\s*\[\]", "", result)
        result = re.sub(r"\. \.", ".", result)
        result = re.sub(r"\(\s*\)", "", result)
        result = re.sub(r",\s*\.", ".", result)
        result = re.sub(r"\s{2,}", " ", result)
        return result.strip()

    def format_reference_list(
        self,
        references: list[ReferenceItem],
    ) -> list[FormattedReference]:
        if not references:
            return []

        ordered = list(references)

        if self.config.reference_order == ReferenceOrder.ALPHABETICAL:
            ordered.sort(key=lambda r: (r.authors[0].last.lower() if r.authors else r.title.lower(), r.year or 0))
        elif self.config.reference_order == ReferenceOrder.CHRONOLOGICAL:
            ordered.sort(key=lambda r: (r.year or 0, r.authors[0].last.lower() if r.authors else ""))

        prefix_format = self.config.reference_prefix_format

        result: list[FormattedReference] = []
        for i, ref in enumerate(ordered):
            num = i + 1
            text = self._fill_template(ref, num)

            if prefix_format:
                prefix = prefix_format.replace("{number}", str(num))
                text = prefix + text

            result.append(
                FormattedReference(
                    number=num,
                    text=text,
                    reference_id=ref.id,
                    doi=ref.doi,
                )
            )

        return result
