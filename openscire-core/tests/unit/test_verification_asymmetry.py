from __future__ import annotations

import contextlib
import os
import tempfile

import pytest
from openscire.constants import ErrorCode
from openscire.ethics.models import (
    Source,
    SourceVerification,
    SourceVerificationStatus,
    VerifiabilityCategory,
    VerificationPath,
)
from openscire.ethics.verification_asymmetry import (
    VerificationAsymmetryTracker,
    categorize_claim,
    compute_asymmetry_gap,
    compute_max_verification_score,
    suggest_verification,
)
from openscire.exceptions import ValidationError

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def tracker() -> VerificationAsymmetryTracker:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    t = VerificationAsymmetryTracker(db_path=path)
    yield t
    t.reset()
    with contextlib.suppress(OSError):
        os.unlink(path)


@pytest.fixture
def verified_sources() -> list[Source]:
    return [
        Source(
            source_id="src1",
            title="Climate change effects on biodiversity",
            abstract="Rising global temperatures have caused measurable shifts in species distribution.",
        ),
        Source(
            source_id="src2",
            title="Gene expression in cancer cells",
            abstract="Overexpression of MYC is associated with poor prognosis in breast cancer.",
        ),
    ]


@pytest.fixture
def verified_verifications() -> list[SourceVerification]:
    return [
        SourceVerification(
            source_id="src1",
            status=SourceVerificationStatus.VERIFIED,
            detail="Matched to source src1.",
            match_score=1.0,
        ),
    ]


@pytest.fixture
def mixed_verifications() -> list[SourceVerification]:
    return [
        SourceVerification(
            source_id="src1",
            status=SourceVerificationStatus.VERIFIED,
            match_score=1.0,
        ),
        SourceVerification(
            source_id="src2",
            status=SourceVerificationStatus.NOT_FOUND,
            match_score=0.0,
        ),
    ]


# =========================================================================
# 3.8.1: Claim categorization — pure function
# =========================================================================


class TestCategorizeClaim:
    def test_verifiable_with_verified_sources(
        self, verified_verifications: list[SourceVerification]
    ) -> None:
        category, reason = categorize_claim(
            "Climate change causes species distribution shifts.",
            verified_verifications,
            confidence_score=0.3,
        )
        assert category == VerifiabilityCategory.VERIFIABLE
        assert "supported by verified sources" in reason

    def test_partial_when_confidence_exceeds_evidence(
        self, mixed_verifications: list[SourceVerification]
    ) -> None:
        category, _ = categorize_claim(
            "Climate change causes species distribution shifts.",
            mixed_verifications,
            confidence_score=0.9,
        )
        assert category == VerifiabilityCategory.PARTIALLY_VERIFIABLE

    def test_partial_with_mixed_sources(
        self, mixed_verifications: list[SourceVerification]
    ) -> None:
        category, _ = categorize_claim(
            "MYC overexpression causes cancer.",
            mixed_verifications,
            confidence_score=0.5,
        )
        assert category == VerifiabilityCategory.PARTIALLY_VERIFIABLE

    def test_non_verifiable_with_retracted(self) -> None:
        retracted = [
            SourceVerification(
                source_id="bad",
                status=SourceVerificationStatus.RETRACTED,
            ),
        ]
        category, reason = categorize_claim(
            "Some discredited claim.",
            retracted,
            confidence_score=0.8,
        )
        assert category == VerifiabilityCategory.NON_VERIFIABLE
        assert "retracted" in reason

    def test_non_verifiable_untestable_language(self) -> None:
        category, reason = categorize_claim(
            "The metaphysical essence of consciousness is unobservable.",
        )
        assert category == VerifiabilityCategory.NON_VERIFIABLE
        assert "untestable" in reason

    def test_non_verifiable_speculative_no_evidence(self) -> None:
        category, reason = categorize_claim(
            "It is tempting to speculate that dark matter might be conscious.",
        )
        assert category == VerifiabilityCategory.NON_VERIFIABLE
        assert "speculative" in reason

    def test_non_verifiable_empty_claim(self) -> None:
        category, reason = categorize_claim("")
        assert category == VerifiabilityCategory.NON_VERIFIABLE
        assert "Empty" in reason

    def test_partial_no_citations_known_domain(self) -> None:
        category, _ = categorize_claim(
            "Gene expression levels determine cell fate.",
        )
        assert category == VerifiabilityCategory.PARTIALLY_VERIFIABLE

    def test_non_verifiable_outside_domain(self) -> None:
        category, _ = categorize_claim(
            "The aesthetic value of sunsets is objectively measurable.",
        )
        assert category == VerifiabilityCategory.NON_VERIFIABLE

    def test_partial_citations_none_verified(self) -> None:
        not_found = [SourceVerification(source_id="x", status=SourceVerificationStatus.NOT_FOUND)]
        category, _ = categorize_claim("Some claim.", not_found)
        assert category == VerifiabilityCategory.PARTIALLY_VERIFIABLE


# =========================================================================
# compute_asymmetry_gap
# =========================================================================


class TestComputeAsymmetryGap:
    def test_no_verifications_returns_confidence(self) -> None:
        assert compute_asymmetry_gap(0.8, []) == 0.8

    def test_verified_gap_small(self, verified_verifications: list[SourceVerification]) -> None:
        gap = compute_asymmetry_gap(0.3, verified_verifications)
        assert gap == pytest.approx(0.3 - 0.9)

    def test_mixed_gap(self, mixed_verifications: list[SourceVerification]) -> None:
        gap = compute_asymmetry_gap(0.5, mixed_verifications)
        assert gap == pytest.approx(0.5 - 0.9)

    def test_retracted_negative_score(self) -> None:
        retracted = [SourceVerification(source_id="x", status=SourceVerificationStatus.RETRACTED)]
        gap = compute_asymmetry_gap(0.5, retracted)
        assert gap == pytest.approx(0.5 - (-0.5))

    def test_zero_confidence(self, verified_verifications: list[SourceVerification]) -> None:
        gap = compute_asymmetry_gap(0.0, verified_verifications)
        assert gap < 0


class TestComputeMaxVerificationScore:
    def test_empty_returns_zero(self) -> None:
        assert compute_max_verification_score([]) == 0.0

    def test_verified_returns_09(self, verified_verifications: list[SourceVerification]) -> None:
        assert compute_max_verification_score(verified_verifications) == 0.9

    def test_mixed_returns_max(self, mixed_verifications: list[SourceVerification]) -> None:
        assert compute_max_verification_score(mixed_verifications) == 0.9

    def test_retracted_only(self) -> None:
        r = [SourceVerification(source_id="x", status=SourceVerificationStatus.RETRACTED)]
        assert compute_max_verification_score(r) == -0.5


# =========================================================================
# 3.8.4: Verification path suggestions — pure function
# =========================================================================


class TestSuggestVerification:
    def test_matches_gene_keyword(self) -> None:
        paths = suggest_verification("The gene expression pattern changes.")
        assert len(paths) <= 3
        assert all(isinstance(p, VerificationPath) for p in paths)

    def test_generic_verifiable_path(self) -> None:
        paths = suggest_verification(
            "The sunset is orange.",
            category=VerifiabilityCategory.VERIFIABLE,
        )
        assert len(paths) >= 1
        assert "confirmatory" in paths[0].approach

    def test_generic_partial_path(self) -> None:
        paths = suggest_verification(
            "Something about biology.",
            category=VerifiabilityCategory.PARTIALLY_VERIFIABLE,
        )
        assert len(paths) >= 1

    def test_generic_non_verifiable_path(self) -> None:
        paths = suggest_verification(
            "Metaphysical essence.",
            category=VerifiabilityCategory.NON_VERIFIABLE,
        )
        assert len(paths) >= 1
        assert "Reformulate" in paths[0].approach

    def test_capped_at_three(self) -> None:
        paths = suggest_verification(
            "Gene protein binding computational drug cell signaling network.",
        )
        assert len(paths) <= 3

    def path_has_correct_type(self) -> None:
        paths = suggest_verification("Gene mutation.")
        assert all(p.category == VerifiabilityCategory.VERIFIABLE for p in paths)


# =========================================================================
# VerificationAsymmetryTracker — integration
# =========================================================================


class TestTrackerCategorizeClaim:
    def test_categorize_returns_record(self, tracker: VerificationAsymmetryTracker) -> None:
        record = tracker.categorize_claim(
            "Gene expression determines cell fate.",
            confidence_score=0.5,
        )
        assert record.claim_hash
        assert record.category in VerifiabilityCategory
        assert record.db_id is not None

    def test_categorize_verifiable(
        self,
        tracker: VerificationAsymmetryTracker,
        verified_verifications: list[SourceVerification],
    ) -> None:
        record = tracker.categorize_claim(
            "Climate change causes species shifts.",
            verifications=verified_verifications,
            confidence_score=0.3,
        )
        assert record.category == VerifiabilityCategory.VERIFIABLE

    def test_categorize_with_paths(self, tracker: VerificationAsymmetryTracker) -> None:
        record = tracker.categorize_claim(
            "Gene expression changes in cancer.",
            confidence_score=0.5,
        )
        assert len(record.verification_paths) > 0

    def test_categorize_persists_to_db(self, tracker: VerificationAsymmetryTracker) -> None:
        tracker.categorize_claim("Claim one.", confidence_score=0.5)
        tracker.categorize_claim("Claim two.", confidence_score=0.3)
        report = tracker.build_report()
        assert report.total_claims == 2


class TestTrackerReEvaluate:
    def test_re_evaluate_adds_new_record(self, tracker: VerificationAsymmetryTracker) -> None:
        first = tracker.categorize_claim("Test claim.", confidence_score=0.8)
        second = tracker.re_evaluate("Test claim.", confidence_score=0.3)
        assert first.db_id != second.db_id
        history = tracker.get_claim_history("Test claim.")
        assert len(history) == 2

    def test_re_evaluate_status_revised(self, tracker: VerificationAsymmetryTracker) -> None:
        tracker.categorize_claim("Gene expression.", confidence_score=0.8)
        verifications = [
            SourceVerification(source_id="s", status=SourceVerificationStatus.VERIFIED),
        ]
        second = tracker.re_evaluate(
            "Gene expression.", verifications=verifications, confidence_score=0.3
        )
        assert second.status.value == "revised"

    def test_re_evaluate_status_confirmed(
        self,
        tracker: VerificationAsymmetryTracker,
        verified_verifications: list[SourceVerification],
    ) -> None:
        tracker.categorize_claim("Climate claim.", confidence_score=0.9)
        record = tracker.re_evaluate(
            "Climate claim.",
            verifications=verified_verifications,
            confidence_score=0.3,
        )
        assert record.status.value == "revised"

    def test_get_claim_history_empty(self, tracker: VerificationAsymmetryTracker) -> None:
        history = tracker.get_claim_history("Never tracked.")
        assert history == []


class TestTrackerBuildReport:
    def test_empty_report(self, tracker: VerificationAsymmetryTracker) -> None:
        report = tracker.build_report()
        assert report.total_claims == 0
        assert report.verification_rate == 0.0

    def test_report_counts(
        self,
        tracker: VerificationAsymmetryTracker,
        verified_verifications: list[SourceVerification],
    ) -> None:
        tracker.categorize_claim("V1", verifications=verified_verifications, confidence_score=0.3)
        tracker.categorize_claim("V2", verifications=verified_verifications, confidence_score=0.9)
        tracker.categorize_claim("Speculative might be maybe.", confidence_score=0.5)
        report = tracker.build_report()
        assert report.total_claims == 3
        assert report.n_verifiable >= 1
        assert report.n_non_verifiable >= 1

    def test_report_verification_rate(
        self,
        tracker: VerificationAsymmetryTracker,
        verified_verifications: list[SourceVerification],
    ) -> None:
        tracker.categorize_claim("V1", verifications=verified_verifications, confidence_score=0.3)
        report = tracker.build_report()
        assert report.verification_rate > 0

    def test_report_gap_stats(self, tracker: VerificationAsymmetryTracker) -> None:
        tracker.categorize_claim("High conf no evidence.", confidence_score=0.9)
        report = tracker.build_report()
        assert report.max_asymmetry_gap > 0


class TestTrackerRaiseIfAsymmetric:
    def test_raises_when_gap_exceeds(self, tracker: VerificationAsymmetryTracker) -> None:
        record = tracker.categorize_claim("High conf no ev.", confidence_score=0.9)
        with pytest.raises(ValidationError) as exc:
            tracker.raise_if_asymmetric(record)
        assert exc.value.error_code == ErrorCode.VALIDATION_ASYMMETRY_DETECTED

    def test_no_raise_when_gap_low(
        self,
        tracker: VerificationAsymmetryTracker,
        verified_verifications: list[SourceVerification],
    ) -> None:
        record = tracker.categorize_claim(
            "Low conf verified.", verifications=verified_verifications, confidence_score=0.3
        )
        tracker.raise_if_asymmetric(record)


class TestTrackerSuggestVerification:
    def test_delegates_to_pure_function(self, tracker: VerificationAsymmetryTracker) -> None:
        paths = tracker.suggest_verification("Gene expression.", VerifiabilityCategory.VERIFIABLE)
        assert len(paths) > 0
        assert all(isinstance(p, VerificationPath) for p in paths)

    def test_different_category(self, tracker: VerificationAsymmetryTracker) -> None:
        paths = tracker.suggest_verification("Meta.", VerifiabilityCategory.NON_VERIFIABLE)
        assert any("Reformulate" in p.approach for p in paths)
