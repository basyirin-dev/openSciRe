"""Integration test: confabulation detection -> flag -> KnowledgeBoundaryFlag -> report.

Verifies the full cycle: running ConfabulationDetector on claims produces
flags with KnowledgeBoundaryFlag attachments, builds a ConfabulationReport,
and auto-escalation triggers on high hallucination rates.
"""

from __future__ import annotations

from openscire.ethics.confabulation import ConfabulationDetector
from openscire.ethics.models import (
    ConfabulationType,
    Source,
)
from openscire.models.philosophy import BoundaryCategory
from openscire.quantification.models import ClaimConfidence


class TestDetectionBoundaryReportCycle:
    """Full cycle: detection -> KnowledgeBoundaryFlag -> ConfabulationReport."""

    def test_detection_to_boundary_to_report_cycle(self, tmp_path: object) -> None:
        db = str(tmp_path / "confab.db")
        detector = ConfabulationDetector(db_path=db, boundary_confidence_threshold=0.3)

        claims = [
            "Enzyme X catalyzes ATP synthesis rapidly.",
            "Enzyme X does not catalyze ATP synthesis rapidly.",
        ]
        sources = [
            Source(
                source_id="s1",
                title="ATP Synthesis Review",
                authors="Smith, J",
                year=2023,
                abstract="Enzyme X catalyzes ATP synthesis efficiently.",
            ),
        ]

        report = detector.check_claims(
            claim_texts=claims,
            claim_confidences=[
                ClaimConfidence(claim_text=claims[0], confidence_score=0.95),
                ClaimConfidence(claim_text=claims[1], confidence_score=0.25),
            ],
            sources=sources,
            domain="biochemistry",
        )

        # Flagged for contradiction (claim-vs-claim)
        assert report.n_flagged >= 1
        assert len(report.flags) >= 1
        assert any(f.flag_type == ConfabulationType.CONTRADICTS_CLAIM for f in report.flags)

        # Low-confidence flagged claim gets KnowledgeBoundaryFlag
        assert len(report.boundaries) >= 1
        assert any(
            b.category == BoundaryCategory.confabulation_suspected for b in report.boundaries
        )

        # Report fields populated
        assert report.total_claims == 2
        assert report.n_flagged == len(report.flags)
        assert len(report.contradictions) >= 1

    def test_auto_escalation_triggered(self, tmp_path: object) -> None:
        db = str(tmp_path / "auto_esc.db")
        detector = ConfabulationDetector(
            db_path=db,
            domain_hallucination_threshold=0.3,
        )

        claims = [
            "Claim one that has no literature support at all.",
            "Claim two also completely unsupported by any source.",
            "Claim three also lacks any backing in the literature.",
        ]
        # All low-confidence
        confidences = [0.1, 0.2, 0.15]

        report = detector.check_claims(
            claim_texts=claims,
            claim_confidences=[
                ClaimConfidence(claim_text=claims[i], confidence_score=confidences[i])
                for i in range(len(claims))
            ],
            sources=[],
            domain="test_domain",
        )

        # All claims flagged (no literature support)
        assert report.n_flagged == 3
        # Hallucination rate = 3/3 = 1.0 > 0.3 threshold
        assert report.auto_escalated is True

        # Each flagged claim has a recommended action
        for flag in report.flags:
            assert flag.recommended_action in ("discard", "escalate", "retry")

        # Flag types are NO_LITERATURE_SUPPORT
        assert all(f.flag_type == ConfabulationType.NO_LITERATURE_SUPPORT for f in report.flags)
