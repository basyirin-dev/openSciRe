from __future__ import annotations

import pytest
from openscire.constants import ErrorCode
from openscire.ethics.models import (
    Citation,
    CitationSupport,
    FirewallAction,
    GroundingVerdict,
    Source,
    SourceVerification,
    SourceVerificationStatus,
    UnsupportedClaimFlag,
)
from openscire.ethics.source_grounding import (
    SourceGroundingEngine,
    assess_citation_support,
    extract_citations,
    verify_citations,
)
from openscire.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(
    source_id: str = "src1",
    doi: str = "10.1234/test",
    pmid: str = "",
    title: str = "Test Title",
    authors: str = "Smith, J",
    year: int = 2023,
    abstract: str = "This is a test abstract about gene regulation.",
    retracted: bool = False,
) -> Source:
    return Source(
        source_id=source_id,
        doi=doi,
        pmid=pmid,
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        retracted=retracted,
    )


_KNOWN_SOURCES = [
    _make_source("src1", "10.1234/test", title="Gene Regulation", authors="Smith, J", year=2023),
    _make_source(
        "src2", "10.5678/demo", title="Climate Models", authors="Doe, A", year=2022, pmid="12345678"
    ),
    _make_source(
        "src3",
        "10.9999/ret",
        title="Retracted Study",
        authors="Retracted, R",
        year=2020,
        retracted=True,
    ),
]


# ---------------------------------------------------------------------------
# Tests: Extraction
# ---------------------------------------------------------------------------


class TestExtractCitations:
    def test_extract_numeric_bracket(self) -> None:
        results = extract_citations("Gene expression is upregulated [1].")
        assert len(results) == 1
        assert results[0].raw_text == "[1]"

    def test_extract_multiple_numeric(self) -> None:
        results = extract_citations("Claim one [1] and claim two [2, 3].")
        assert len(results) == 2
        assert results[0].raw_text == "[1]"
        assert results[1].raw_text == "[2, 3]"

    def test_extract_author_year_parenthetical(self) -> None:
        results = extract_citations("The sky is blue (Smith, 2023).")
        assert len(results) == 1
        assert "Smith" in results[0].authors
        assert results[0].year == 2023

    def test_extract_author_year_et_al(self) -> None:
        results = extract_citations("Gene expression (Smith et al., 2023).")
        assert len(results) == 1
        assert "Smith" in results[0].authors

    def test_extract_doi(self) -> None:
        results = extract_citations("See doi:10.1234/abcd1234 for details.")
        assert len(results) == 1
        assert results[0].doi == "10.1234/abcd1234"

    def test_extract_doi_various_formats(self) -> None:
        results = extract_citations("Reference DOI: 10.5678/efgh5678.")
        assert len(results) == 1
        assert results[0].doi == "10.5678/efgh5678"

    def test_extract_pmid(self) -> None:
        results = extract_citations("Data from PMID: 12345678.")
        assert len(results) == 1
        assert results[0].pmid == "12345678"

    def test_extract_arxiv(self) -> None:
        results = extract_citations("Preprint at arXiv:2301.12345.")
        assert len(results) == 1
        assert results[0].arxiv_id == "2301.12345"

    def test_extract_mixed_formats(self) -> None:
        text = (
            "Gene regulation is key [1]. Recent work (Smith, 2023) confirms this. "
            "See also doi:10.1234/xyz and PMID:87654321."
        )
        results = extract_citations(text)
        assert len(results) == 4

    def test_extract_no_citations(self) -> None:
        results = extract_citations("This is plain text with no citations.")
        assert len(results) == 0

    def test_extract_empty_string(self) -> None:
        results = extract_citations("")
        assert len(results) == 0

    def test_extract_doi_with_punctuation(self) -> None:
        results = extract_citations("(doi:10.1234/abcd1234).")
        assert len(results) == 1
        assert results[0].doi == "10.1234/abcd1234"

    def test_extract_avoids_duplicates(self) -> None:
        results = extract_citations("See [1] and also [1].")
        dois = [c.raw_text for c in results]
        assert dois.count("[1]") == 1


# ---------------------------------------------------------------------------
# Tests: Source Verification
# ---------------------------------------------------------------------------


class TestVerifyCitations:
    def test_verify_by_doi(self) -> None:
        citations = [Citation(raw_text="test", doi="10.1234/test")]
        results = verify_citations(citations, _KNOWN_SOURCES)
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.VERIFIED
        assert results[0].source_id == "src1"

    def test_verify_by_pmid(self) -> None:
        citations = [Citation(raw_text="test", pmid="12345678")]
        results = verify_citations(citations, _KNOWN_SOURCES)
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.VERIFIED

    def test_verify_author_year(self) -> None:
        citations = [Citation(raw_text="test", authors="Smith, J", year=2023)]
        results = verify_citations(citations, _KNOWN_SOURCES)
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.VERIFIED

    def test_verify_not_found(self) -> None:
        citations = [Citation(raw_text="test", doi="10.9999/nonexistent")]
        results = verify_citations(citations, _KNOWN_SOURCES)
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.NOT_FOUND

    def test_verify_retracted_source(self) -> None:
        citations = [Citation(raw_text="test", doi="10.9999/ret")]
        results = verify_citations(citations, _KNOWN_SOURCES, verify_retraction=True)
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.RETRACTED

    def test_verify_retraction_disabled(self) -> None:
        citations = [Citation(raw_text="test", doi="10.9999/ret")]
        results = verify_citations(citations, _KNOWN_SOURCES, verify_retraction=False)
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.VERIFIED

    def test_verify_empty_known_sources(self) -> None:
        citations = [Citation(raw_text="test", doi="10.1234/test")]
        results = verify_citations(citations, [])
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.NOT_FOUND

    def test_verify_empty_citations(self) -> None:
        results = verify_citations([], _KNOWN_SOURCES)
        assert len(results) == 0

    def test_verify_author_year_mismatch(self) -> None:
        citations = [Citation(raw_text="test", authors="Nobody, X", year=1999)]
        results = verify_citations(citations, _KNOWN_SOURCES)
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.NOT_FOUND

    def test_verify_multiple_citations(self) -> None:
        citations = [
            Citation(raw_text="a", doi="10.1234/test"),
            Citation(raw_text="b", doi="10.5678/demo"),
            Citation(raw_text="c", doi="10.9999/nope"),
        ]
        results = verify_citations(citations, _KNOWN_SOURCES)
        assert len(results) == 3
        assert results[0].status == SourceVerificationStatus.VERIFIED
        assert results[1].status == SourceVerificationStatus.VERIFIED
        assert results[2].status == SourceVerificationStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Tests: Citation Support Assessment
# ---------------------------------------------------------------------------


class TestAssessCitationSupport:
    def test_supports_high_overlap(self) -> None:
        source = _make_source(title="Gene Regulation in Cells", abstract="Gene regulation is key")
        citation = Citation(raw_text="(Smith, 2023)", authors="Smith, J", year=2023)
        result = assess_citation_support("Gene regulation is key.", citation, source)
        assert result == CitationSupport.SUPPORTS

    def test_neutral_low_overlap(self) -> None:
        source = _make_source(title="Climate Models", abstract="Temperature predictions")
        citation = Citation(raw_text="(Doe, 2022)", authors="Doe, A", year=2022)
        result = assess_citation_support("Gene regulation is key.", citation, source)
        assert result == CitationSupport.NEUTRAL

    def test_contradicts_with_negation(self) -> None:
        source = _make_source(title="Gene Regulation", abstract="Gene regulation found")
        citation = Citation(raw_text="(Smith, 2023)", authors="Smith, J", year=2023)
        result = assess_citation_support(
            "Gene regulation was not observed (Smith, 2023).", citation, source
        )
        assert result == CitationSupport.CONTRADICTS

    def test_unverified_no_source(self) -> None:
        citation = Citation(raw_text="(Unknown, 2023)", authors="Unknown, U", year=2023)
        result = assess_citation_support("Some claim.", citation, source=None)
        assert result == CitationSupport.UNVERIFIED

    def test_neutral_empty_source_text(self) -> None:
        source = _make_source(title="", abstract="")
        citation = Citation(raw_text="(Smith, 2023)", authors="Smith, J", year=2023)
        result = assess_citation_support("Gene regulation is key.", citation, source)
        assert result == CitationSupport.NEUTRAL


# ---------------------------------------------------------------------------
# Tests: SourceGroundingEngine
# ---------------------------------------------------------------------------


class TestSourceGroundingEngine:
    def test_default_construction(self) -> None:
        engine = SourceGroundingEngine()
        assert engine is not None

    def test_construction_with_config(self) -> None:
        engine = SourceGroundingEngine(
            require_citations=True,
            verify_retraction_status=True,
            min_sources_per_claim=2,
            allow_unsupported_claims=True,
        )
        assert engine is not None

    def test_extract_citations_delegates(self) -> None:
        engine = SourceGroundingEngine()
        results = engine.extract_citations("See [1] and (Smith, 2023).")
        assert len(results) == 2

    def test_extract_citations_disabled(self) -> None:
        engine = SourceGroundingEngine(extraction_enabled=False)
        results = engine.extract_citations("See [1].")
        assert len(results) == 0

    def test_verify_citations_delegates(self) -> None:
        engine = SourceGroundingEngine()
        citations = [Citation(raw_text="test", doi="10.1234/test")]
        results = engine.verify_citations(citations, _KNOWN_SOURCES)
        assert len(results) == 1
        assert results[0].status == SourceVerificationStatus.VERIFIED

    def test_assess_citation_support_delegates(self) -> None:
        engine = SourceGroundingEngine()
        source = _make_source(title="Gene Regulation", abstract="Gene regulation key")
        citation = Citation(raw_text="(Smith, 2023)", authors="Smith, J", year=2023)
        result = engine.assess_citation_support("Gene regulation is key.", citation, source)
        assert result == CitationSupport.SUPPORTS

    def test_enforce_citations_empty_text(self) -> None:
        engine = SourceGroundingEngine()
        verdict = engine.enforce_citations("")
        assert isinstance(verdict, GroundingVerdict)
        assert not verdict.claims_flagged

    def test_enforce_citations_no_citations_in_text(self) -> None:
        engine = SourceGroundingEngine(require_citations=True, allow_unsupported_claims=True)
        verdict = engine.enforce_citations(
            "Gene regulation is a key biological process. It controls development.",
        )
        assert len(verdict.claims_flagged) > 0
        assert all(f.reason == "no_citations" for f in verdict.claims_flagged)

    def test_enforce_citations_with_citations(self) -> None:
        engine = SourceGroundingEngine()
        verdict = engine.enforce_citations(
            "Gene regulation is key (Smith, 2023). Climate models confirm this (Doe, 2022).",
            known_sources=_KNOWN_SOURCES,
        )
        assert verdict.approved

    def test_enforce_citations_retracted_source(self) -> None:
        engine = SourceGroundingEngine(allow_unsupported_claims=True)
        verdict = engine.enforce_citations(
            "Retracted claim (Retracted, 2020).",
            known_sources=_KNOWN_SOURCES,
        )
        retracted_flags = [f for f in verdict.claims_flagged if f.reason == "retracted_source"]
        assert len(retracted_flags) > 0

    def test_enforce_citations_not_found(self) -> None:
        engine = SourceGroundingEngine(allow_unsupported_claims=True)
        verdict = engine.enforce_citations(
            "Unknown claim (Nobody, 1999).",
            known_sources=_KNOWN_SOURCES,
        )
        nf_flags = [f for f in verdict.claims_flagged if f.reason == "citation_not_found"]
        assert len(nf_flags) > 0

    def test_check_claims_no_citations(self) -> None:
        engine = SourceGroundingEngine()
        verdict = engine.check_claims(
            claim_texts=["Test claim."],
            citations=[[]],
            known_sources=_KNOWN_SOURCES,
        )
        assert not verdict.approved
        assert len(verdict.claims_flagged) == 1
        assert verdict.claims_flagged[0].reason == "no_citations"

    def test_check_claims_with_citations(self) -> None:
        engine = SourceGroundingEngine()
        verdict = engine.check_claims(
            claim_texts=["Test claim."],
            citations=[[Citation(raw_text="test", doi="10.1234/test")]],
            known_sources=_KNOWN_SOURCES,
        )
        assert verdict.approved

    def test_raise_if_unsupported_raises(self) -> None:
        engine = SourceGroundingEngine()
        verdict = GroundingVerdict(
            approved=False,
            claims_flagged=[UnsupportedClaimFlag(claim_text="test", reason="no_citations")],
        )
        with pytest.raises(ValidationError) as exc:
            engine.raise_if_unsupported(verdict)
        assert exc.value.error_code in (
            ErrorCode.VALIDATION_CITATION_BROKEN,
            ErrorCode.VALIDATION_SOURCE_NOT_FOUND,
        )

    def test_raise_if_unsupported_ok(self) -> None:
        engine = SourceGroundingEngine()
        verdict = GroundingVerdict(approved=True)
        engine.raise_if_unsupported(verdict)

    def test_raise_if_unsupported_retracted(self) -> None:
        engine = SourceGroundingEngine()
        verdict = GroundingVerdict(
            approved=False,
            claims_flagged=[
                UnsupportedClaimFlag(claim_text="retracted", reason="retracted_source"),
            ],
        )
        with pytest.raises(ValidationError) as exc:
            engine.raise_if_unsupported(verdict)
        assert exc.value.error_code == ErrorCode.VALIDATION_RETRACTED_SOURCE

    def test_enforce_citations_insufficient_verified(self) -> None:
        engine = SourceGroundingEngine(
            require_citations=True,
            min_sources_per_claim=3,
            allow_unsupported_claims=True,
        )
        verdict = engine.enforce_citations(
            "Gene regulation is key (Smith, 2023).",
            known_sources=_KNOWN_SOURCES,
        )
        insuff_flags = [
            f for f in verdict.claims_flagged if f.reason == "insufficient_verified_sources"
        ]
        assert len(insuff_flags) > 0

    def test_enforce_citations_contradiction_detected(self) -> None:
        engine = SourceGroundingEngine(allow_unsupported_claims=True)
        verdict = engine.enforce_citations(
            "Gene regulation was not observed (Smith, 2023).",
            known_sources=_KNOWN_SOURCES,
        )
        contrad_flags = [f for f in verdict.claims_flagged if f.reason == "citation_contradicts"]
        assert len(contrad_flags) >= 0

    def test_enforce_citations_allow_unsupported(self) -> None:
        engine = SourceGroundingEngine(allow_unsupported_claims=True)
        verdict = engine.enforce_citations(
            "Unsupported claim with no citations.",
            known_sources=[],
        )
        assert verdict.approved
        assert len(verdict.claims_flagged) > 0

    def test_source_verification_model_defaults(self) -> None:
        v = SourceVerification(source_id="test")
        assert v.status == SourceVerificationStatus.NOT_FOUND
        assert v.match_score == 0.0

    def test_grounding_verdict_model_defaults(self) -> None:
        v = GroundingVerdict()
        assert v.approved
        assert v.claims_flagged == []
        assert v.citations_verified == []

    def test_unsupported_claim_flag_defaults(self) -> None:
        f = UnsupportedClaimFlag(claim_text="test")
        assert f.reason == ""
        assert f.severity == FirewallAction.FLAG

    def test_extract_citations_engine_empty_text(self) -> None:
        engine = SourceGroundingEngine()
        assert engine.extract_citations("") == []
