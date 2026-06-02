from __future__ import annotations

import contextlib
import os
import tempfile

import pytest
from openscire.constants import ErrorCode
from openscire.ethics.confabulation import ConfabulationDetector
from openscire.ethics.models import (
    ConfabulationFlag,
    ConfabulationReport,
    ConfabulationType,
    HallucinationRecord,
    Source,
)
from openscire.exceptions import ValidationError
from openscire.models.philosophy import BoundaryCategory, KnowledgeBoundaryFlag
from openscire.quantification.models import ClaimConfidence

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def detector() -> ConfabulationDetector:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    d = ConfabulationDetector(db_path=path)
    yield d
    with contextlib.suppress(OSError):
        os.unlink(path)


@pytest.fixture
def sources() -> list[Source]:
    return [
        Source(
            source_id="s1",
            title="Climate change impacts on Arctic ecosystems",
            abstract="Rising temperatures in the Arctic have led to sea ice decline and shifts in species ranges.",
        ),
        Source(
            source_id="s2",
            title="MYC oncogene in breast cancer",
            abstract="MYC overexpression is correlated with poor prognosis in breast cancer patients.",
        ),
        Source(
            source_id="s3",
            title="CRISPR-Cas9 gene editing efficiency",
            abstract="CRISPR-Cas9 enables precise genome editing with high efficiency in mammalian cells.",
        ),
    ]


@pytest.fixture
def sample_flags() -> list[ConfabulationFlag]:
    return [
        ConfabulationFlag(
            claim_text="Unsupported claim about X.",
            flag_type=ConfabulationType.NO_LITERATURE_SUPPORT,
            severity=0.6,
            confidence=0.2,
            recommended_action="escalate",
        ),
        ConfabulationFlag(
            claim_text="Contradictory claim about Y.",
            flag_type=ConfabulationType.CONTRADICTS_LITERATURE,
            severity=0.8,
            contradicted_by="Source says opposite.",
            confidence=0.1,
            recommended_action="discard",
        ),
    ]


# =========================================================================
# ConfabulationType enum
# =========================================================================


class TestConfabulationType:
    def test_has_four_values(self) -> None:
        values = set(ConfabulationType)
        assert len(values) == 4

    def test_contradicts_claim(self) -> None:
        assert ConfabulationType.CONTRADICTS_CLAIM == "contradicts_claim"

    def test_contradicts_literature(self) -> None:
        assert ConfabulationType.CONTRADICTS_LITERATURE == "contradicts_literature"

    def test_no_literature_support(self) -> None:
        assert ConfabulationType.NO_LITERATURE_SUPPORT == "no_literature_support"

    def test_confidence_too_low(self) -> None:
        assert ConfabulationType.CONFIDENCE_TOO_LOW == "confidence_too_low"


# =========================================================================
# Claim-vs-Claim detection (Pass 1)
# =========================================================================


class TestDetectClaimContradictions:
    def test_no_contradiction_single_claim(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["Single claim."])
        assert len(report.contradictions) == 0

    def test_no_contradiction_unrelated(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["Apples are fruit.", "The sky is blue."])
        assert len(report.contradictions) == 0

    def test_direct_contradiction_detected(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(
            [
                "CRISPR-Cas9 enables precise genome editing in mammalian cells.",
                "CRISPR-Cas9 does not enable precise genome editing in mammalian cells.",
            ]
        )
        assert len(report.flags) >= 1
        contradiction_flags = [
            f for f in report.flags if f.flag_type == ConfabulationType.CONTRADICTS_CLAIM
        ]
        assert len(contradiction_flags) >= 1

    def test_contradiction_flag_has_recommended_action(
        self, detector: ConfabulationDetector
    ) -> None:
        report = detector.check_claims(
            [
                "A is true.",
                "A is not true.",
            ]
        )
        assert len(report.flags) >= 1
        assert report.flags[0].recommended_action in ("retry", "escalate", "discard")

    def test_multiple_contradictions(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(
            [
                "A is true.",
                "A is not true.",
                "B is true.",
                "B is not true.",
            ]
        )
        assert len(report.contradictions) >= 2


# =========================================================================
# Claim-vs-Literature detection (Pass 2)
# =========================================================================


class TestDetectLiteratureConfabulations:
    def test_supported_claim_not_flagged(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["Rising temperatures in the Arctic have led to sea ice decline."],
            sources=sources,
        )
        lit_flags = [
            f
            for f in report.flags
            if f.flag_type
            in (
                ConfabulationType.NO_LITERATURE_SUPPORT,
                ConfabulationType.CONTRADICTS_LITERATURE,
            )
        ]
        assert len(lit_flags) == 0

    def test_unsupported_claim_flagged(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["Quantum entanglement allows faster-than-light communication."],
            sources=sources,
        )
        lit_flags = [
            f for f in report.flags if f.flag_type == ConfabulationType.NO_LITERATURE_SUPPORT
        ]
        assert len(lit_flags) >= 1

    def test_contradicts_literature_flagged(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["MYC overexpression is not correlated with poor prognosis in breast cancer."],
            sources=sources,
        )
        contradict_flags = [
            f for f in report.flags if f.flag_type == ConfabulationType.CONTRADICTS_LITERATURE
        ]
        assert len(contradict_flags) >= 1

    def test_no_sources_returns_unsupported(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["Some unsupported claim."])
        lit_flags = [
            f for f in report.flags if f.flag_type == ConfabulationType.NO_LITERATURE_SUPPORT
        ]
        assert len(lit_flags) >= 1

    def test_empty_sources_returns_unsupported(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["Some unsupported claim."], sources=[])
        lit_flags = [
            f for f in report.flags if f.flag_type == ConfabulationType.NO_LITERATURE_SUPPORT
        ]
        assert len(lit_flags) >= 1

    def test_partial_overlap_below_threshold(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["Unicorns exist and control the weather patterns completely independently."],
            sources=sources,
        )
        lit_flags = [
            f for f in report.flags if f.flag_type == ConfabulationType.NO_LITERATURE_SUPPORT
        ]
        assert len(lit_flags) >= 1

    def test_flag_has_contradicted_by_text(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["MYC overexpression is not correlated with poor prognosis."],
            sources=sources,
        )
        contradict_flags = [
            f for f in report.flags if f.flag_type == ConfabulationType.CONTRADICTS_LITERATURE
        ]
        if contradict_flags:
            assert contradict_flags[0].contradicted_by

    def test_severity_scaled_correctly(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["Totally unrelated fantastical claim about dragons."],
            sources=sources,
        )
        lit_flags = [
            f for f in report.flags if f.flag_type == ConfabulationType.NO_LITERATURE_SUPPORT
        ]
        if lit_flags:
            assert 0 < lit_flags[0].severity <= 1.0


# =========================================================================
# Full detection pipeline
# =========================================================================


class TestCheckClaims:
    def test_empty_claims(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims([])
        assert report.total_claims == 0
        assert report.n_flagged == 0

    def test_returns_report_type(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["A claim."])
        assert isinstance(report, ConfabulationReport)

    def test_report_has_timestamp(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["A claim."])
        assert report.timestamp

    def test_all_clean_claims(self, detector: ConfabulationDetector, sources: list[Source]) -> None:
        report = detector.check_claims(
            ["Rising temperatures in the Arctic have led to sea ice decline."],
            sources=sources,
        )
        assert report.n_flagged == 0

    def test_mixed_claims(self, detector: ConfabulationDetector, sources: list[Source]) -> None:
        report = detector.check_claims(
            [
                "Rising temperatures in the Arctic have led to sea ice decline.",
                "CRISPR-Cas9 enables precise genome editing in mammalian cells.",
                "Unicorns are real and control the weather.",
            ],
            sources=sources,
        )
        assert report.n_flagged >= 1
        assert report.total_claims == 3

    def test_with_confidences(self, detector: ConfabulationDetector, sources: list[Source]) -> None:
        confidences = [
            ClaimConfidence(claim_text="Unicorns are real.", confidence_score=0.1),
        ]
        report = detector.check_claims(
            ["Unicorns are real."],
            sources=sources,
            claim_confidences=confidences,
        )
        assert report.n_flagged >= 1

    def test_domain_propagation(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(
            ["Made up claim about X."],
            domain="genetics",
        )
        assert report.domain == "genetics"

    def test_no_duplicate_flag_types(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["MYC overexpression is not correlated with poor prognosis."],
            sources=sources,
        )
        types = [f.flag_type for f in report.flags]
        assert len(types) == len(set(types))


# =========================================================================
# Historical tracking + auto-escalation (3.9.2)
# =========================================================================


class TestHistoricalTracking:
    def test_record_flag_persists(self, detector: ConfabulationDetector) -> None:
        flag = ConfabulationFlag(
            claim_text="Test.",
            flag_type=ConfabulationType.NO_LITERATURE_SUPPORT,
            severity=0.5,
        )
        detector.record_flag("biology", flag)
        stats = detector.get_domain_stats("biology")
        assert stats.n_flags >= 1

    def test_domain_stats_empty(self, detector: ConfabulationDetector) -> None:
        stats = detector.get_domain_stats("nonexistent")
        assert stats.n_flags == 0
        assert stats.by_type == {}

    def test_domain_stats_breakdown(self, detector: ConfabulationDetector) -> None:
        detector.record_flag(
            "bio",
            ConfabulationFlag(
                claim_text="A",
                flag_type=ConfabulationType.NO_LITERATURE_SUPPORT,
                severity=0.5,
            ),
        )
        detector.record_flag(
            "bio",
            ConfabulationFlag(
                claim_text="B",
                flag_type=ConfabulationType.CONTRADICTS_LITERATURE,
                severity=0.7,
            ),
        )
        stats = detector.get_domain_stats("bio")
        assert stats.n_flags == 2
        assert len(stats.by_type) == 2

    def test_multiple_domains_separate(self, detector: ConfabulationDetector) -> None:
        detector.record_flag(
            "physics",
            ConfabulationFlag(
                claim_text="A",
                flag_type=ConfabulationType.NO_LITERATURE_SUPPORT,
                severity=0.5,
            ),
        )
        stats = detector.get_domain_stats("biology")
        assert stats.n_flags == 0

    def test_auto_escalation_triggered(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        d = ConfabulationDetector(db_path=path, domain_hallucination_threshold=0.1)
        for _ in range(10):
            d.record_flag(
                "risky",
                ConfabulationFlag(
                    claim_text="X",
                    flag_type=ConfabulationType.NO_LITERATURE_SUPPORT,
                    severity=0.5,
                ),
            )
        report = d.check_claims(
            ["Another unsupported claim."],
            domain="risky",
            sources=[],
        )
        assert report.auto_escalated is True
        with contextlib.suppress(OSError):
            os.unlink(path)

    def test_auto_escalation_not_triggered(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["CRISPR-Cas9 enables precise genome editing with high efficiency in mammalian cells."],
            domain="safe",
            sources=sources,
        )
        assert report.auto_escalated is False

    def test_hallucination_stats_in_report(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(
            ["Bad claim about X.", "Another bad claim about Y."],
            domain="test_domain",
            sources=[],
        )
        assert isinstance(report.hallucination_stats, HallucinationRecord)
        assert report.hallucination_stats.domain == "test_domain"


# =========================================================================
# Knowledge boundary flagging (3.9.3)
# =========================================================================


class TestKnowledgeBoundaryFlagging:
    def test_boundary_attached_when_low_confidence(self, detector: ConfabulationDetector) -> None:
        confidences = [
            ClaimConfidence(claim_text="Unsupported claim about X.", confidence_score=0.1),
        ]
        report = detector.check_claims(
            ["Unsupported claim about X."],
            claim_confidences=confidences,
        )
        assert len(report.boundaries) >= 1
        assert isinstance(report.boundaries[0], KnowledgeBoundaryFlag)

    def test_boundary_not_attached_when_high_confidence(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        confidences = [
            ClaimConfidence(
                claim_text="Rising temperatures in the Arctic have led to sea ice decline.",
                confidence_score=0.8,
            ),
        ]
        report = detector.check_claims(
            ["Rising temperatures in the Arctic have led to sea ice decline."],
            sources=sources,
            claim_confidences=confidences,
        )
        assert len(report.boundaries) == 0

    def test_boundary_uses_confabulation_category(self, detector: ConfabulationDetector) -> None:
        confidences = [
            ClaimConfidence(claim_text="Low confidence claim.", confidence_score=0.05),
        ]
        report = detector.check_claims(
            ["Low confidence claim."],
            claim_confidences=confidences,
        )
        if report.boundaries:
            assert report.boundaries[0].category == BoundaryCategory.confabulation_suspected

    def test_boundary_has_detail_text(self, detector: ConfabulationDetector) -> None:
        confidences = [
            ClaimConfidence(claim_text="Low confidence claim.", confidence_score=0.1),
        ]
        report = detector.check_claims(
            ["Low confidence claim."],
            claim_confidences=confidences,
        )
        if report.boundaries:
            assert "below boundary threshold" in report.boundaries[0].detail

    def test_multiple_boundaries(self, detector: ConfabulationDetector) -> None:
        confidences = [
            ClaimConfidence(claim_text="Low A.", confidence_score=0.1),
            ClaimConfidence(claim_text="Low B.", confidence_score=0.2),
        ]
        report = detector.check_claims(
            ["Low A.", "Low B."],
            claim_confidences=confidences,
        )
        assert len(report.boundaries) >= 1

    def test_boundary_threshold_respected(self, detector: ConfabulationDetector) -> None:
        confidences = [
            ClaimConfidence(claim_text="Borderline claim.", confidence_score=0.35),
        ]
        report = detector.check_claims(
            ["Borderline claim."],
            claim_confidences=confidences,
        )
        assert len(report.boundaries) == 0


# =========================================================================
# Confabulation report + recommended actions (3.9.4)
# =========================================================================


class TestConfabulationReport:
    def test_report_counts(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(
            ["Supported claim.", "Unsupported fantastical claim."],
            sources=[],
        )
        assert report.total_claims == 2
        assert report.n_flagged >= 1

    def test_recommended_action_retry(self, detector: ConfabulationDetector) -> None:
        flags = [
            ConfabulationFlag(
                claim_text="Low severity.",
                flag_type=ConfabulationType.NO_LITERATURE_SUPPORT,
                severity=0.1,
                confidence=0.0,
                recommended_action="retry",
            ),
        ]
        assert flags[0].recommended_action == "retry"

    def test_recommended_action_escalate(self) -> None:
        flag = ConfabulationFlag(
            claim_text="Medium severity.",
            flag_type=ConfabulationType.CONTRADICTS_CLAIM,
            severity=0.5,
            recommended_action="escalate",
        )
        assert flag.recommended_action == "escalate"

    def test_recommended_action_discard(self) -> None:
        flag = ConfabulationFlag(
            claim_text="High severity.",
            flag_type=ConfabulationType.CONTRADICTS_LITERATURE,
            severity=0.9,
            recommended_action="discard",
        )
        assert flag.recommended_action == "discard"

    def test_report_serializable(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["A claim."])
        d = report.model_dump()
        assert d["total_claims"] == 1
        assert d["n_flagged"] >= 0

    def test_report_with_all_fields(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        confidences = [
            ClaimConfidence(claim_text="Low confidence unsupported claim.", confidence_score=0.1),
            ClaimConfidence(claim_text="A does not cause B.", confidence_score=0.5),
        ]
        report = detector.check_claims(
            [
                "Low confidence unsupported claim.",
                "A does not cause B.",
                "Rising temperatures in the Arctic have led to sea ice decline.",
            ],
            sources=sources,
            claim_confidences=confidences,
            domain="testing",
        )
        assert report.total_claims == 3
        assert len(report.flags) >= 1
        assert len(report.boundaries) >= 1
        assert isinstance(report.hallucination_stats, HallucinationRecord)


# =========================================================================
# raise_if_confabulation
# =========================================================================


class TestRaiseIfConfabulation:
    def test_raises_when_flagged(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["Unsupported fantastical claim."])
        with pytest.raises(ValidationError) as exc:
            detector.raise_if_confabulation(report)
        assert exc.value.error_code == ErrorCode.VALIDATION_CONFABULATION_DETECTED

    def test_no_raise_when_clean(
        self, detector: ConfabulationDetector, sources: list[Source]
    ) -> None:
        report = detector.check_claims(
            ["Rising temperatures in the Arctic have led to sea ice decline."],
            sources=sources,
        )
        detector.raise_if_confabulation(report)


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    def test_empty_string_claim(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims([""])
        assert report.total_claims == 1

    def test_whitespace_only(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["   "])
        assert report.total_claims == 1

    def test_very_short_claim(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["Hi."])
        assert report.total_claims == 1

    def test_no_confidences_provided(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(
            ["A claim."],
            claim_confidences=None,
        )
        assert report.total_claims == 1

    def test_confidences_mismatch_count(self, detector: ConfabulationDetector) -> None:
        confidences = [
            ClaimConfidence(claim_text="Claim A.", confidence_score=0.1),
        ]
        report = detector.check_claims(
            ["Claim A.", "Claim B.", "Claim C."],
            claim_confidences=confidences,
        )
        assert report.total_claims == 3

    def test_unicode_claims(self, detector: ConfabulationDetector) -> None:
        report = detector.check_claims(["über科学研究 claim about 基因表达。"])
        assert report.total_claims == 1
