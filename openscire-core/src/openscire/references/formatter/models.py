from __future__ import annotations

import enum

from pydantic import BaseModel


class CitationStyle(str, enum.Enum):
    APA = "apa"
    NATURE = "nature"
    SCIENCE = "science"
    VANCOUVER = "vancouver"
    IEEE = "ieee"
    CHICAGO = "chicago"
    ACS = "acs"
    CUSTOM = "custom"


class InlineFormat(str, enum.Enum):
    AUTHOR_YEAR_PAREN = "author_year_paren"
    AUTHOR_YEAR_NOPAREN = "author_year_noparen"
    NUMERIC_BRACKET = "numeric_bracket"
    NUMERIC_SUPERSCRIPT = "numeric_superscript"
    AUTHOR_NUMERIC = "author_numeric"


class ReferenceOrder(str, enum.Enum):
    ALPHABETICAL = "alphabetical"
    ORDER_OF_APPEARANCE = "order_of_appearance"
    CHRONOLOGICAL = "chronological"


class AuthorFormat(str, enum.Enum):
    LAST_FIRST = "last_first"
    FIRST_LAST = "first_last"
    LAST_FIRST_FULL = "last_first_full"
    FULL = "full"


class StyleConfig(BaseModel):
    name: str = "custom"
    display_name: str = ""
    inline_format: InlineFormat = InlineFormat.AUTHOR_YEAR_PAREN
    reference_order: ReferenceOrder = ReferenceOrder.ALPHABETICAL
    author_format: AuthorFormat = AuthorFormat.LAST_FIRST
    et_al_threshold: int = 3
    use_ampersand: bool = False
    journal_italic: bool = True
    volume_italic: bool = True
    doi_links: bool = True
    doi_prefix: str = "https://doi.org/"
    include_issue: bool = True
    max_authors: int = 10
    reference_prefix_format: str = ""
    format_template: str = ""


class FormattedCitation(BaseModel):
    text: str = ""
    reference_number: int | None = None
    style: str = ""


class FormattedReference(BaseModel):
    number: int = 0
    text: str = ""
    reference_id: str = ""
    doi: str = ""
