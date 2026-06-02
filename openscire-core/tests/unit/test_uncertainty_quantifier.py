import pytest
from openscire.constants import ErrorCode
from openscire.exceptions import ValidationError
from openscire.provider.models import Chunk
from openscire.quantification import (
    ClaimConfidence,
    Contradiction,
    ContradictionDetector,
    ContradictionType,
    DisclosedClaim,
    KnowledgeBoundary,
    ModelUncertainty,
    SourceQuality,
    UncertaintyQuantifier,
    UncertaintyReport,
)


class TestSourceQuality:
    def test_all_members(self) -> None:
        assert SourceQuality.PEER_REVIEWED == "peer_reviewed"
        assert SourceQuality.PREPRINT == "preprint"
        assert SourceQuality.GRAY_LITERATURE == "gray_literature"
        assert SourceQuality.ANECDOTAL == "anecdotal"
        assert SourceQuality.UNKNOWN == "unknown"


class TestModelsConstruction:
    def test_claim_confidence_defaults(self) -> None:
        cc = ClaimConfidence(claim_text="test claim")
        assert cc.confidence_score == 0.0
        assert cc.model_confidence_score == 0.5
        assert cc.evidence_count == 0

    def test_contradiction_defaults(self) -> None:
        c = Contradiction(claim_a="a", claim_b="b")
        assert c.contradiction_type == ContradictionType.DIRECT
        assert c.severity == 0.0

    def test_knowledge_boundary(self) -> None:
        kb = KnowledgeBoundary(query="test", category="insufficient_literature")
        assert kb.category == "insufficient_literature"

    def test_model_uncertainty_defaults(self) -> None:
        mu = ModelUncertainty()
        assert mu.available is False

    def test_uncertainty_report_defaults(self) -> None:
        ur = UncertaintyReport()
        assert ur.claims == []
        assert ur.overall_confidence == 0.0

    def test_disclosed_claim_defaults(self) -> None:
        dc = DisclosedClaim(claim="test")
        assert dc.disclosure == ""


class TestContradictionDetector:
    def test_empty_claims(self) -> None:
        detector = ContradictionDetector()
        assert detector.detect([]) == []

    def test_single_claim_no_contradiction(self) -> None:
        detector = ContradictionDetector()
        claims = [ClaimConfidence(claim_text="The sky is blue.")]
        assert detector.detect(claims) == []

    def test_contradictory_claims(self) -> None:
        detector = ContradictionDetector(threshold=0.3)
        claims = [
            ClaimConfidence(claim_text="The sky is blue."),
            ClaimConfidence(claim_text="The sky is not blue.", confidence_score=0.8),
        ]
        results = detector.detect(claims)
        assert len(results) == 1
        assert results[0].contradiction_type == ContradictionType.DIRECT

    def test_direct_contradiction_detected(self) -> None:
        detector = ContradictionDetector(threshold=0.3)
        claims = [
            ClaimConfidence(claim_text="Vaccines cause autism."),
            ClaimConfidence(claim_text="Vaccines do not cause autism.", confidence_score=0.9),
        ]
        results = detector.detect(claims)
        assert len(results) >= 1
        assert results[0].severity > 0.3

    def test_threshold_filters_low_severity(self) -> None:
        detector = ContradictionDetector(threshold=0.9)
        claims = [
            ClaimConfidence(claim_text="Apples are fruits."),
            ClaimConfidence(claim_text="Apples are not vegetables.", confidence_score=0.7),
        ]
        results = detector.detect(claims)
        assert len(results) == 0

    def test_per_call_threshold_override(self) -> None:
        detector = ContradictionDetector(threshold=0.9)
        claims = [
            ClaimConfidence(claim_text="Apples are fruits."),
            ClaimConfidence(claim_text="Apples are not fruits.", confidence_score=0.8),
        ]
        results = detector.detect(claims, threshold=0.1)
        assert len(results) >= 1

    def test_identical_claims_no_contradiction(self) -> None:
        detector = ContradictionDetector(threshold=0.1)
        claims = [
            ClaimConfidence(claim_text="Apples are fruits."),
            ClaimConfidence(claim_text="Apples are fruits.", confidence_score=0.9),
        ]
        results = detector.detect(claims)
        assert len(results) == 0

    def test_negation_markers(self) -> None:
        assert ContradictionDetector._has_negation("is not true") is True
        assert ContradictionDetector._has_negation("doesn't work") is True
        assert ContradictionDetector._has_negation("never happens") is True
        assert ContradictionDetector._has_negation("confirms the theory") is False
        assert ContradictionDetector._has_negation("no evidence found") is True
        assert ContradictionDetector._has_negation("disprove the claim") is True


class TestUncertaintyQuantifier:
    def test_default_construction(self) -> None:
        uq = UncertaintyQuantifier()
        assert uq is not None

    def test_score_claim_no_sources(self) -> None:
        uq = UncertaintyQuantifier()
        cc = uq.score_claim("Test claim.")
        assert cc.confidence_score < 0.5
        assert cc.source_quality_score == 0.0
        assert cc.agreement_score == 0.0
        assert cc.model_confidence_score == 0.5

    def test_score_claim_with_sources(self) -> None:
        uq = UncertaintyQuantifier()
        sources = [
            {"quality": "peer_reviewed"},
            {"quality": "peer_reviewed"},
        ]
        cc = uq.score_claim("Test claim.", sources=sources)
        assert cc.source_quality_score == 0.9
        assert cc.agreement_score == 1.0
        assert cc.evidence_count == 2

    def test_score_claim_with_retracted_source(self) -> None:
        uq = UncertaintyQuantifier()
        sources = [
            {"quality": "peer_reviewed", "retracted": True},
        ]
        cc = uq.score_claim("Test claim.", sources=sources)
        assert cc.source_quality_score == 0.4

    def test_score_claim_with_contradictions(self) -> None:
        uq = UncertaintyQuantifier()
        sources = [
            {"quality": "peer_reviewed"},
            {"quality": "peer_reviewed", "contradicts": True},
        ]
        cc = uq.score_claim("Test claim.", sources=sources)
        assert cc.agreement_score == 0.5
        assert cc.contradictory_count == 1

    def test_model_confidence_from_logprobs(self) -> None:
        uq = UncertaintyQuantifier()
        logprobs = {"token1": -0.1, "token2": -0.2, "token3": -0.3}
        sources = [{"quality": "peer_reviewed"}]
        cc = uq.score_claim("Test claim.", sources=sources, logprobs=logprobs)
        assert cc.model_confidence_score > 0.5

    def test_model_confidence_neutral_when_no_logprobs(self) -> None:
        uq = UncertaintyQuantifier()
        cc = uq.score_claim("Test claim.")
        assert cc.model_confidence_score == 0.5

    def test_evidence_density(self) -> None:
        uq = UncertaintyQuantifier()
        cc1 = uq.score_claim("C1", sources=[{"quality": "peer_reviewed"}])
        cc10 = uq.score_claim("C10", sources=[{"quality": "peer_reviewed"}] * 10)
        assert cc10.evidence_density_score > cc1.evidence_density_score
        assert cc1.evidence_density_score > 0.0

    def test_confidence_interval_lower_bound(self) -> None:
        uq = UncertaintyQuantifier()
        cc = uq.score_claim("Test claim.")
        assert cc.confidence_interval[0] <= cc.confidence_score
        assert cc.confidence_interval[1] >= cc.confidence_score

    def test_disclose_returns_disclosed_claim(self) -> None:
        uq = UncertaintyQuantifier()
        dc = uq.disclose("Test claim.", sources=[{"quality": "peer_reviewed"}])
        assert isinstance(dc, DisclosedClaim)
        assert dc.claim == "Test claim."
        assert "Confidence:" in dc.disclosure
        assert "Sources:" in dc.disclosure

    def test_disclose_low_confidence(self) -> None:
        uq = UncertaintyQuantifier()
        dc = uq.disclose("Test claim.")
        assert dc.confidence.confidence_score < 0.5
        assert "Confidence:" in dc.disclosure

    def test_require_confidence_passes(self) -> None:
        uq = UncertaintyQuantifier()
        disclosure = uq.require_confidence("Test claim.", min_confidence=0.0)
        assert "Confidence:" in disclosure

    def test_require_confidence_fails(self) -> None:
        uq = UncertaintyQuantifier()
        with pytest.raises(ValidationError) as exc:
            uq.require_confidence("Nonsense claim.", min_confidence=0.9)
        assert exc.value.error_code == ErrorCode.UNCERTAINTY_INSUFFICIENT

    def test_check_boundary_no_sources(self) -> None:
        uq = UncertaintyQuantifier()
        boundary = uq.check_boundary("What is the answer?", n_sources=0)
        assert boundary is not None
        assert boundary.category == "insufficient_literature"

    def test_check_boundary_with_sources(self) -> None:
        uq = UncertaintyQuantifier()
        boundary = uq.check_boundary("What is the answer?", n_sources=5)
        assert boundary is None

    def test_check_boundary_unanswerable_pattern(self) -> None:
        uq = UncertaintyQuantifier()
        boundary = uq.check_boundary("What would happen if gravity stopped?", n_sources=1)
        assert boundary is not None
        assert boundary.category == "in_principle_unanswerable"

    def test_extract_uncertainty_no_logprobs(self) -> None:
        uq = UncertaintyQuantifier()
        mu = uq.extract_uncertainty()
        assert mu.available is False

    def test_extract_uncertainty_with_logprobs(self) -> None:
        uq = UncertaintyQuantifier()
        logprobs = {"the": -0.1, "sky": -0.2, "is": -0.3, "blue": -0.4}
        mu = uq.extract_uncertainty(logprobs=logprobs)
        assert mu.available is True
        assert mu.mean_logprob < 0.0
        assert mu.perplexity > 0.0

    def test_extract_uncertainty_perplexity(self) -> None:
        uq = UncertaintyQuantifier()
        lp = {"a": -0.1, "b": -0.1}
        mu = uq.extract_uncertainty(logprobs=lp)
        expected = 2.718**0.1
        assert abs(mu.perplexity - expected) < 0.1

    def test_extract_uncertainty_refusal_detected(self) -> None:
        uq = UncertaintyQuantifier()
        logprobs = {"I": -0.1, "cannot": -0.2, "answer": -0.3}
        mu = uq.extract_uncertainty(logprobs=logprobs)
        assert mu.refusal_detected is True
        assert mu.refusal_pattern == "i cannot"

    def test_extract_uncertainty_no_refusal(self) -> None:
        uq = UncertaintyQuantifier()
        logprobs = {"The": -0.1, "answer": -0.2, "is": -0.3, "42": -0.4}
        mu = uq.extract_uncertainty(logprobs=logprobs)
        assert mu.refusal_detected is False

    def test_extract_from_chunks(self) -> None:
        uq = UncertaintyQuantifier()
        chunks = [
            Chunk(logprobs={"hello": -0.1}),
            Chunk(logprobs={"world": -0.2}),
        ]
        mu = uq.extract_uncertainty(chunks=chunks)
        assert mu.available is True
        assert abs(mu.mean_logprob - (-0.15)) < 0.001

    def test_build_report_no_claims(self) -> None:
        uq = UncertaintyQuantifier()
        report = uq.build_report(claims=[], query="test")
        assert report.overall_confidence == 0.0
        assert len(report.boundaries) == 1

    def test_build_report_with_claims(self) -> None:
        uq = UncertaintyQuantifier()
        claims = [
            uq.score_claim("Claim one.", sources=[{"quality": "peer_reviewed"}]),
            uq.score_claim("Claim two.", sources=[{"quality": "preprint"}]),
        ]
        report = uq.build_report(claims, query="test query")
        assert len(report.claims) == 2
        assert report.overall_confidence > 0.0

    def test_build_report_detects_boundary(self) -> None:
        uq = UncertaintyQuantifier()
        report = uq.build_report(claims=[], query="What would happen if X?")
        assert len(report.boundaries) == 1

    def test_build_report_with_contradictions(self) -> None:
        uq = UncertaintyQuantifier(contradiction_threshold=0.3)
        claims = [
            uq.score_claim("Vaccines cause autism.", sources=[{"quality": "preprint"}]),
            uq.score_claim("Vaccines do not cause autism.", sources=[{"quality": "peer_reviewed"}]),
        ]
        report = uq.build_report(claims, query="Do vaccines cause autism?")
        assert len(report.contradictions) >= 1

    def test_format_report_no_claims(self) -> None:
        uq = UncertaintyQuantifier()
        report = uq.build_report([], query="")
        text = uq.format_report(report)
        assert "Confidence:" in text

    def test_format_report_with_claims(self) -> None:
        uq = UncertaintyQuantifier()
        claims = [uq.score_claim("Test.", sources=[{"quality": "peer_reviewed"}])]
        report = uq.build_report(claims)
        text = uq.format_report(report)
        assert "Confidence:" in text
        assert "Claims:" in text

    def test_format_report_contradictions(self) -> None:
        uq = UncertaintyQuantifier(contradiction_threshold=0.3)
        c1 = uq.score_claim("A is true.", sources=[{"quality": "peer_reviewed"}])
        c2 = uq.score_claim("A is not true.", sources=[{"quality": "peer_reviewed"}])
        report = uq.build_report([c1, c2])
        text = uq.format_report(report)
        assert "Contradictions" in text

    def test_format_report_boundary(self) -> None:
        uq = UncertaintyQuantifier()
        report = uq.build_report([], query="unanswerable speculation")
        text = uq.format_report(report)
        assert "BOUNDARY" in text

    def test_score_sources_batch(self) -> None:
        uq = UncertaintyQuantifier()
        sources = [
            {"quality": "peer_reviewed"},
            {"quality": "preprint"},
            {"quality": "gray_literature"},
            {"quality": "unknown"},
        ]
        scores = uq.score_sources_batch(sources)
        assert len(scores) == 4
        assert scores[0] == 0.9
        assert scores[1] == 0.6
        assert scores[2] == 0.3
        assert scores[3] == 0.0

    def test_overall_confidence_penalized_by_contradictions(self) -> None:
        uq = UncertaintyQuantifier(contradiction_threshold=0.3)
        c1 = uq.score_claim("A is true.", sources=[{"quality": "peer_reviewed"}])
        c2 = uq.score_claim("A is not true.", sources=[{"quality": "peer_reviewed"}])
        report = uq.build_report([c1, c2])
        mean_no_penalty = (c1.confidence_score + c2.confidence_score) / 2
        assert report.overall_confidence < mean_no_penalty

    def test_confidence_bar(self) -> None:
        bar = UncertaintyQuantifier._confidence_bar(0.5, width=10)
        assert bar == "█████░░░░░"

    def test_confidence_bar_full(self) -> None:
        bar = UncertaintyQuantifier._confidence_bar(1.0, width=10)
        assert bar == "██████████"

    def test_confidence_bar_empty(self) -> None:
        bar = UncertaintyQuantifier._confidence_bar(0.0, width=10)
        assert bar == "░░░░░░░░░░"
