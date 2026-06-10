"""Tests for SourceEnforcer, CitationMode, and related models."""

from openscire.ethics.models import Source
from openscire.references.enforcer import (
    CitationMode,
    CitationSuggestion,
    SourceEnforcementReport,
    SourceEnforcer,
    UnsupportedClaim,
)

_SOURCES = [
    Source(
        source_id="ref1",
        doi="10.1000/abc123",
        title="DNA Methylation in Cancer",
        authors="Smith",
        year=2020,
    ),
    Source(
        source_id="ref2",
        doi="10.1000/def456",
        title="Gene Expression Regulation",
        authors="Jones",
        year=2021,
    ),
    Source(
        source_id="ref3",
        doi="10.1000/ghi789",
        title="Retracted Study on Cell Division",
        authors="Lee",
        year=2019,
        retracted=True,
    ),
]


class TestCitationMode:
    def test_values(self) -> None:
        assert CitationMode.STRICT.value == "strict"
        assert CitationMode.WARN.value == "warn"
        assert CitationMode.AUDIT.value == "audit"

    def test_enum_members(self) -> None:
        assert len(CitationMode) == 3


class TestModels:
    def test_citation_suggestion_defaults(self) -> None:
        s = CitationSuggestion()
        assert s.claim_text == ""
        assert s.confidence == 0.0
        assert s.authors == ""

    def test_unsupported_claim_defaults(self) -> None:
        c = UnsupportedClaim()
        assert c.claim_text == ""
        assert c.reason == ""
        assert c.suggestions == []

    def test_report_defaults(self) -> None:
        r = SourceEnforcementReport()
        assert r.mode == CitationMode.AUDIT
        assert r.approved is True
        assert r.total_sentences == 0


class TestParsing:
    def test_extracts_author_year(self) -> None:
        enforcer = SourceEnforcer()
        text = "DNA methylation is key (Smith, 2020)."
        report = enforcer.enforce(text, _SOURCES)
        assert report.verified_citations >= 1

    def test_extracts_multiple_citations(self) -> None:
        enforcer = SourceEnforcer()
        text = "First finding (Smith, 2020). Second finding (Jones, 2021)."
        report = enforcer.enforce(text, _SOURCES)
        assert report.verified_citations >= 2

    def test_doi_citation(self) -> None:
        enforcer = SourceEnforcer()
        text = "The study doi: 10.1000/abc123 found evidence."
        report = enforcer.enforce(text, _SOURCES)
        assert report.verified_citations >= 1


class TestVerification:
    def test_verified_citation_not_flagged(self) -> None:
        enforcer = SourceEnforcer()
        text = "DNA methylation is key (Smith, 2020)."
        report = enforcer.enforce(text, _SOURCES)
        assert len(report.unsupported_claims) == 0
        assert report.cited_sentences == 1

    def test_unverified_citation_flagged(self) -> None:
        enforcer = SourceEnforcer()
        text = "Unknown result (Nobody, 2099)."
        report = enforcer.enforce(text, _SOURCES)
        assert len(report.unsupported_claims) == 1
        assert report.unsupported_claims[0].reason == "citation_not_found"

    def test_retracted_citation_flagged(self) -> None:
        enforcer = SourceEnforcer()
        text = "The retracted study found (Lee, 2019)."
        report = enforcer.enforce(text, _SOURCES)
        assert len(report.unsupported_claims) == 1
        assert report.unsupported_claims[0].reason == "retracted"


class TestUnsupportedClaims:
    def test_no_citation_flagged(self) -> None:
        enforcer = SourceEnforcer()
        text = "This claim has no supporting citation."
        report = enforcer.enforce(text, _SOURCES)
        assert len(report.unsupported_claims) == 1
        assert report.unsupported_claims[0].reason == "no_citation"

    def test_mixed_text(self) -> None:
        enforcer = SourceEnforcer()
        text = (
            "DNA methylation regulates cancer (Smith, 2020). "
            "This is an unsupported claim. "
            "Gene expression is important (Jones, 2021)."
        )
        report = enforcer.enforce(text, _SOURCES)
        unsupported = [c for c in report.unsupported_claims if c.reason == "no_citation"]
        assert len(unsupported) == 1
        assert report.cited_sentences == 2

    def test_all_cited_no_flags(self) -> None:
        enforcer = SourceEnforcer()
        text = "Cancer research (Smith, 2020). Gene regulation (Jones, 2021)."
        report = enforcer.enforce(text, _SOURCES)
        assert len(report.unsupported_claims) == 0


class TestSuggestion:
    def test_suggests_relevant_source(self) -> None:
        enforcer = SourceEnforcer()
        text = "DNA methylation plays a key role in cancer development."
        report = enforcer.enforce(text, _SOURCES)
        assert len(report.unsupported_claims) == 1
        claim = report.unsupported_claims[0]
        assert len(claim.suggestions) >= 1
        suggested_ids = {s.suggested_reference_id for s in claim.suggestions}
        assert "ref1" in suggested_ids

    def test_no_suggestion_when_no_overlap(self) -> None:
        enforcer = SourceEnforcer()
        text = "Quantum computing in astrophysics."
        report = enforcer.enforce(text, _SOURCES)
        assert len(report.unsupported_claims) == 1
        assert len(report.unsupported_claims[0].suggestions) == 0

    def test_suggestions_ranked_by_confidence(self) -> None:
        enforcer = SourceEnforcer()
        text = "DNA gene expression regulation."
        report = enforcer.enforce(text, _SOURCES)
        claim = report.unsupported_claims[0]
        confidences = [s.confidence for s in claim.suggestions]
        assert confidences == sorted(confidences, reverse=True)

    def test_suggestions_limited_to_top_3(self) -> None:
        many_sources = _SOURCES + [
            Source(source_id="ref4", title="DNA Research Further", authors="Wang", year=2022),
            Source(source_id="ref5", title="Advanced DNA Methods", authors="Zhang", year=2023),
            Source(source_id="ref6", title="DNA New Frontiers", authors="Liu", year=2024),
        ]
        enforcer = SourceEnforcer()
        text = "DNA research methods and frontiers."
        report = enforcer.enforce(text, many_sources)
        claim = report.unsupported_claims[0]
        assert len(claim.suggestions) <= 3


class TestModes:
    def test_strict_blocks_unsupported(self) -> None:
        enforcer = SourceEnforcer()
        text = "Unsupported claim with no citation."
        report = enforcer.enforce(text, _SOURCES, mode=CitationMode.STRICT)
        assert report.approved is False

    def test_strict_allows_when_all_cited(self) -> None:
        enforcer = SourceEnforcer()
        text = "Cancer research (Smith, 2020)."
        report = enforcer.enforce(text, _SOURCES, mode=CitationMode.STRICT)
        assert report.approved is True

    def test_warn_allows_with_suggestions(self) -> None:
        enforcer = SourceEnforcer()
        text = "Unsupported claim with no citation."
        report = enforcer.enforce(text, _SOURCES, mode=CitationMode.WARN)
        assert report.approved is True
        assert len(report.unsupported_claims) >= 1

    def test_audit_allows_with_suggestions(self) -> None:
        enforcer = SourceEnforcer()
        text = "Unsupported claim with no citation."
        report = enforcer.enforce(text, _SOURCES, mode=CitationMode.AUDIT)
        assert report.approved is True
        assert len(report.unsupported_claims) >= 1

    def test_strict_empty_text_allowed(self) -> None:
        enforcer = SourceEnforcer()
        report = enforcer.enforce("", _SOURCES, mode=CitationMode.STRICT)
        assert report.approved is True

    def test_strict_whitespace_only_allowed(self) -> None:
        enforcer = SourceEnforcer()
        report = enforcer.enforce("   ", _SOURCES, mode=CitationMode.STRICT)
        assert report.approved is True


class TestEdgeCases:
    def test_empty_text(self) -> None:
        enforcer = SourceEnforcer()
        report = enforcer.enforce("", _SOURCES)
        assert report.total_sentences == 0
        assert report.approved is True

    def test_no_citations_at_all(self) -> None:
        enforcer = SourceEnforcer()
        text = "This is a factual statement. This is another statement."
        report = enforcer.enforce(text, _SOURCES)
        assert report.total_sentences == 2
        assert len(report.unsupported_claims) == 2

    def test_no_known_sources(self) -> None:
        enforcer = SourceEnforcer()
        text = "Finding (Smith, 2020)."
        report = enforcer.enforce(text, [])
        assert report.verified_citations == 0
        assert len(report.unsupported_claims) == 1
        assert report.unsupported_claims[0].reason == "citation_not_found"

    def test_all_citations_verified(self) -> None:
        enforcer = SourceEnforcer()
        text = "Methylation (Smith, 2020). Expression (Jones, 2021)."
        report = enforcer.enforce(text, _SOURCES)
        assert report.verified_citations == 2
        assert report.unverified_citations == 0
        assert len(report.unsupported_claims) == 0
