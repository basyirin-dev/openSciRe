"""Tests for CitationFormatter, export formatters, and style models."""

import json

import pytest

from openscire.references.formatter import (
    AuthorFormat,
    BUILT_IN_STYLES,
    CitationFormatter,
    CitationStyle,
    FormattedCitation,
    FormattedReference,
    InlineFormat,
    ReferenceOrder,
    StyleConfig,
    to_bibtex,
    to_csl_json,
    to_ris,
)
from openscire.references.formatter.bibtex import _generate_citekey
from openscire.references.formatter.formatter import _format_authors
from openscire.references.formatter.models import (
    CitationStyle as CS,
    InlineFormat as IF,
    ReferenceOrder as RO,
)
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_A1 = ReferenceAuthor(first="John", last="Smith")
_A2 = ReferenceAuthor(first="Jane", last="Doe")
_A3 = ReferenceAuthor(first="Bob", last="Jones")
_A4 = ReferenceAuthor(first="Alice", last="Brown")

_REF_EMPTY = ReferenceItem(id="empty", source=ReferenceSource.bibtex)

_REF1 = ReferenceItem(
    id="ref1",
    source=ReferenceSource.bibtex,
    doi="10.1000/abc123",
    title="DNA Methylation in Cancer",
    authors=[_A1, _A2],
    journal="Nature Genetics",
    year=2020,
    volume="15",
    issue="3",
    pages="123-130",
    publisher="Springer",
    url="https://example.com/ref1",
    keywords=["cancer", "methylation"],
    item_type="journal_article",
)

_REF2 = ReferenceItem(
    id="ref2",
    source=ReferenceSource.bibtex,
    doi="10.1000/def456",
    title="Gene Expression Regulation",
    authors=[_A3],
    journal="Cell",
    year=2021,
    volume="185",
    issue="1",
    pages="45-60",
    publisher="Elsevier",
    item_type="journal_article",
)

_REF3 = ReferenceItem(
    id="ref3",
    source=ReferenceSource.bibtex,
    doi="10.1000/ghi789",
    title="Computational Biology Methods",
    authors=[_A4, _A1, _A2, _A3],
    journal="Bioinformatics",
    year=2019,
    volume="35",
    issue="10",
    pages="200-210",
    publisher="Oxford UP",
    item_type="book",
)

_REFERENCES = [_REF1, _REF2, _REF3]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestStyleConfig:
    def test_defaults(self) -> None:
        c = StyleConfig()
        assert c.name == "custom"
        assert c.inline_format == InlineFormat.AUTHOR_YEAR_PAREN

    def test_custom_values(self) -> None:
        c = StyleConfig(
            name="test",
            inline_format=InlineFormat.NUMERIC_BRACKET,
            reference_order=ReferenceOrder.ORDER_OF_APPEARANCE,
            doi_prefix="doi:",
        )
        assert c.name == "test"
        assert c.doi_prefix == "doi:"


class TestBuiltInStyles:
    def test_all_builtin_styles_defined(self) -> None:
        builtin = {CitationStyle.APA, CitationStyle.NATURE, CitationStyle.SCIENCE,
                   CitationStyle.VANCOUVER, CitationStyle.IEEE, CitationStyle.CHICAGO,
                   CitationStyle.ACS}
        for style in builtin:
            assert style in BUILT_IN_STYLES, f"Missing style: {style}"

    def test_apa_has_correct_config(self) -> None:
        c = BUILT_IN_STYLES[CitationStyle.APA]
        assert c.inline_format == InlineFormat.AUTHOR_YEAR_PAREN
        assert c.reference_order == ReferenceOrder.ALPHABETICAL

    def test_nature_uses_superscript(self) -> None:
        c = BUILT_IN_STYLES[CitationStyle.NATURE]
        assert c.inline_format == InlineFormat.NUMERIC_SUPERSCRIPT

    def test_vancouver_uses_bracket(self) -> None:
        c = BUILT_IN_STYLES[CitationStyle.VANCOUVER]
        assert c.inline_format == InlineFormat.NUMERIC_BRACKET


# ---------------------------------------------------------------------------
# Author formatting
# ---------------------------------------------------------------------------


class TestFormatAuthors:
    def test_empty(self) -> None:
        assert _format_authors([], AuthorFormat.LAST_FIRST, 3, 10, False) == ""

    def test_single_last_first(self) -> None:
        assert _format_authors([_A1], AuthorFormat.LAST_FIRST, 3, 10, False) == "Smith, J."

    def test_single_first_last(self) -> None:
        assert _format_authors([_A1], AuthorFormat.FIRST_LAST, 3, 10, False) == "J. Smith"

    def test_two_authors_and(self) -> None:
        result = _format_authors([_A1, _A2], AuthorFormat.LAST_FIRST, 3, 10, False)
        assert result == "Smith, J. and Doe, J."

    def test_two_authors_ampersand(self) -> None:
        result = _format_authors([_A1, _A2], AuthorFormat.LAST_FIRST, 3, 10, True)
        assert result == "Smith, J., & Doe, J."

    def test_three_authors_et_al(self) -> None:
        result = _format_authors([_A1, _A2, _A3, _A4], AuthorFormat.LAST_FIRST, 3, 10, False)
        assert result == "Smith, J., Doe, J., Jones, B. and et al."

    def test_et_al_threshold(self) -> None:
        result = _format_authors([_A1, _A2, _A3, _A4], AuthorFormat.LAST_FIRST, 2, 10, False)
        assert "et al." in result
        assert "Brown" not in result

    def test_last_first_full(self) -> None:
        result = _format_authors([_A1], AuthorFormat.LAST_FIRST_FULL, 3, 10, False)
        assert result == "Smith, John"

    def test_full_format(self) -> None:
        result = _format_authors([_A1], AuthorFormat.FULL, 3, 10, False)
        assert result == "John Smith"


# ---------------------------------------------------------------------------
# Inline formatting
# ---------------------------------------------------------------------------


class TestInlineFormatting:
    def test_apa_inline(self) -> None:
        f = CitationFormatter(CitationStyle.APA)
        cit = f.format_inline(_REF1)
        assert cit.text == "(Smith, J., & Doe, J., 2020)"

    def test_apa_single_author(self) -> None:
        f = CitationFormatter(CitationStyle.APA)
        cit = f.format_inline(_REF2)
        assert cit.text == "(Jones, B., 2021)"

    def test_nature_inline(self) -> None:
        f = CitationFormatter(CitationStyle.NATURE)
        cit = f.format_inline(_REF1, number=1)
        assert cit.text == "[1]"

    def test_vancouver_inline(self) -> None:
        f = CitationFormatter(CitationStyle.VANCOUVER)
        cit = f.format_inline(_REF1, number=3)
        assert cit.text == "[3]"

    def test_ieee_inline(self) -> None:
        f = CitationFormatter(CitationStyle.IEEE)
        cit = f.format_inline(_REF1, number=2)
        assert cit.text == "[2]"

    def test_chicago_inline(self) -> None:
        f = CitationFormatter(CitationStyle.CHICAGO)
        cit = f.format_inline(_REF1)
        assert "Smith" in cit.text
        assert "2020" in cit.text

    def test_acs_inline(self) -> None:
        f = CitationFormatter(CitationStyle.ACS)
        cit = f.format_inline(_REF1, number=1)
        assert cit.text == "[1]"

    def test_no_authors_apa(self) -> None:
        f = CitationFormatter(CitationStyle.APA)
        cit = f.format_inline(_REF_EMPTY)
        assert "(n.d.)" in cit.text

    def test_returns_formatted_citation(self) -> None:
        f = CitationFormatter(CitationStyle.VANCOUVER)
        cit = f.format_inline(_REF1, number=5)
        assert isinstance(cit, FormattedCitation)
        assert cit.reference_number == 5
        assert cit.style == "vancouver"


# ---------------------------------------------------------------------------
# Reference list
# ---------------------------------------------------------------------------


class TestReferenceList:
    def test_apa_alphabetical(self) -> None:
        f = CitationFormatter(CitationStyle.APA)
        refs = f.format_reference_list(_REFERENCES)
        assert len(refs) == 3
        # Alphabetical by first author last name: Brown, Jones, Smith
        assert refs[0].reference_id == "ref3"  # Brown
        assert refs[1].reference_id == "ref2"  # Jones
        assert refs[2].reference_id == "ref1"  # Smith

    def test_vancouver_order_of_appearance(self) -> None:
        f = CitationFormatter(CitationStyle.VANCOUVER)
        refs = f.format_reference_list(_REFERENCES)
        assert len(refs) == 3
        assert refs[0].reference_id == "ref1"
        assert refs[1].reference_id == "ref2"
        assert refs[2].reference_id == "ref3"

    def test_vancouver_has_numbered_prefix(self) -> None:
        f = CitationFormatter(CitationStyle.VANCOUVER)
        refs = f.format_reference_list(_REFERENCES)
        assert refs[0].text.startswith("1. ")
        assert refs[1].text.startswith("2. ")
        assert refs[2].text.startswith("3. ")

    def test_apa_no_numbered_prefix(self) -> None:
        f = CitationFormatter(CitationStyle.APA)
        refs = f.format_reference_list(_REFERENCES)
        assert not refs[0].text.startswith("1. ")

    def test_empty_list(self) -> None:
        f = CitationFormatter(CitationStyle.APA)
        assert f.format_reference_list([]) == []

    def test_returns_formatted_reference(self) -> None:
        f = CitationFormatter(CitationStyle.VANCOUVER)
        refs = f.format_reference_list([_REF1])
        assert isinstance(refs[0], FormattedReference)
        assert refs[0].doi == _REF1.doi


# ---------------------------------------------------------------------------
# Constructor / config
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_default_style(self) -> None:
        f = CitationFormatter()
        assert f.style == CitationStyle.APA

    def test_string_style(self) -> None:
        f = CitationFormatter("nature")
        assert f.style == CitationStyle.NATURE

    def test_custom_config_overrides_builtin(self) -> None:
        custom = StyleConfig(name="my", inline_format=InlineFormat.NUMERIC_BRACKET)
        f = CitationFormatter(CitationStyle.APA, custom_config=custom)
        cit = f.format_inline(_REF1, number=7)
        assert cit.text == "[7]"

    def test_invalid_string_falls_back_to_apa(self) -> None:
        f = CitationFormatter("nonexistent")
        assert f.style == CitationStyle.APA


# ---------------------------------------------------------------------------
# BibTeX export
# ---------------------------------------------------------------------------


class TestBibtexExport:
    def test_exports_article_entry(self) -> None:
        result = to_bibtex([_REF1])
        assert "@article{" in result
        assert "author = {" in result
        assert "title = {" in result
        assert "journal = {" in result
        assert "year = {2020}" in result

    def test_exports_book_entry(self) -> None:
        result = to_bibtex([_REF3])
        assert "@book{" in result

    def test_multiple_entries(self) -> None:
        result = to_bibtex(_REFERENCES)
        assert result.count("@") == 3

    def test_empty_list(self) -> None:
        assert to_bibtex([]) == "\n"

    def test_citekey_generation(self) -> None:
        key = _generate_citekey(_REF1)
        assert "Smith" in key
        assert "2020" in key

    def test_author_formatting(self) -> None:
        result = to_bibtex([_REF1])
        assert "Smith, John" in result
        assert "and" in result

    def test_kwargs_included(self) -> None:
        result = to_bibtex([_REF1])
        assert "doi" in result
        assert "url" in result


# ---------------------------------------------------------------------------
# RIS export
# ---------------------------------------------------------------------------


class TestRisExport:
    def test_exports_jour_entry(self) -> None:
        result = to_ris([_REF1])
        assert "TY  - JOUR" in result
        assert "ER  -" in result
        assert result.strip().endswith("ER  -")

    def test_author_tags(self) -> None:
        result = to_ris([_REF1])
        assert "AU  - Smith, John" in result
        assert "AU  - Doe, Jane" in result

    def test_field_tags(self) -> None:
        result = to_ris([_REF1])
        assert "TI  - DNA Methylation in Cancer" in result
        assert "JF  - Nature Genetics" in result
        assert "DO  - 10.1000/abc123" in result
        assert "PY  - 2020" in result

    def test_page_splitting(self) -> None:
        result = to_ris([_REF1])
        assert "SP  - 123" in result
        assert "EP  - 130" in result

    def test_multiple_records(self) -> None:
        result = to_ris(_REFERENCES)
        assert result.count("TY  -") == 3
        assert result.count("ER  -") == 3

    def test_book_type(self) -> None:
        result = to_ris([_REF3])
        assert "TY  - BOOK" in result

    def test_empty_list(self) -> None:
        assert to_ris([]) == "\n"


# ---------------------------------------------------------------------------
# CSL-JSON export
# ---------------------------------------------------------------------------


class TestCslJsonExport:
    def test_exports_valid_json(self) -> None:
        result = to_csl_json([_REF1])
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 1
        item = data[0]
        assert item["id"] == "ref1"
        assert item["type"] == "article-journal"

    def test_author_format(self) -> None:
        result = to_csl_json([_REF1])
        data = json.loads(result)
        authors = data[0]["author"]
        assert len(authors) == 2
        assert authors[0]["family"] == "Smith"
        assert authors[0]["given"] == "John"

    def test_fields_mapped(self) -> None:
        result = to_csl_json([_REF1])
        data = json.loads(result)
        item = data[0]
        assert item["title"] == "DNA Methylation in Cancer"
        assert item["container-title"] == "Nature Genetics"
        assert item["volume"] == "15"
        assert item["issue"] == "3"
        assert item["page"] == "123-130"

    def test_issued_date(self) -> None:
        result = to_csl_json([_REF1])
        data = json.loads(result)
        assert data[0]["issued"]["date-parts"] == [[2020]]

    def test_multiple_items(self) -> None:
        result = to_csl_json(_REFERENCES)
        data = json.loads(result)
        assert len(data) == 3

    def test_empty_list(self) -> None:
        assert json.loads(to_csl_json([])) == []

    def test_book_type(self) -> None:
        result = to_csl_json([_REF3])
        data = json.loads(result)
        assert data[0]["type"] == "book"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_missing_year(self) -> None:
        ref = ReferenceItem(
            id="noyear",
            source=ReferenceSource.bibtex,
            title="No Year Paper",
            authors=[_A1],
        )
        f = CitationFormatter(CitationStyle.APA)
        cit = f.format_inline(ref)
        assert "n.d." in cit.text

    def test_missing_authors(self) -> None:
        ref = ReferenceItem(
            id="noauthor",
            source=ReferenceSource.bibtex,
            title="No Author Paper",
            year=2022,
        )
        f = CitationFormatter(CitationStyle.APA)
        cit = f.format_inline(ref)
        assert "(2022)" in cit.text

    def test_doi_linking_config(self) -> None:
        assert BUILT_IN_STYLES[CitationStyle.APA].doi_prefix == "https://doi.org/"
        assert BUILT_IN_STYLES[CitationStyle.NATURE].doi_prefix == "doi:"

    def test_eight_styles_in_enum(self) -> None:
        assert len(CitationStyle) == 8
