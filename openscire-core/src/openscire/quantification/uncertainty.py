from __future__ import annotations

import math
from typing import Any

from openscire.constants import ErrorCode
from openscire.exceptions import ValidationError
from openscire.logging import get_logger
from openscire.provider.models import Chunk

from .contradiction import ContradictionDetector
from .models import (
    ClaimConfidence,
    DisclosedClaim,
    KnowledgeBoundary,
    ModelUncertainty,
    SourceQuality,
    UncertaintyReport,
)

logger = get_logger("openscire.quantification.uncertainty")

_SOURCE_QUALITY_SCORES: dict[SourceQuality, float] = {
    SourceQuality.PEER_REVIEWED: 0.9,
    SourceQuality.PREPRINT: 0.6,
    SourceQuality.GRAY_LITERATURE: 0.3,
    SourceQuality.ANECDOTAL: 0.1,
    SourceQuality.UNKNOWN: 0.0,
}

_UNANSWERABLE_PATTERNS = [
    "what if",
    "what would happen if",
    "if the future",
    "speculative",
    "cannot be known",
    "unknown at this time",
    "in principle unanswerable",
]

_REFUSAL_PATTERNS = [
    "i cannot",
    "i'm not sure",
    "as an ai",
    "i don't know",
    "i am not able",
    "i cannot answer",
    "i'm unable to",
]


class UncertaintyQuantifier:
    """Quantifies uncertainty of model-generated claims.

    Combines source quality, agreement between sources, model logprob
    signals, and evidence density into composite confidence scores.
    Detects contradictions, flags knowledge boundaries, and produces
    mandatory disclosure strings.
    """

    def __init__(
        self,
        contradiction_threshold: float = 0.6,
        boundary_confidence_threshold: float = 0.3,
        source_quality_overrides: dict[str, float] | None = None,
        retraction_penalty: float = -0.5,
        contradiction_detector: ContradictionDetector | None = None,
        provenance_tracker: Any = None,  # noqa: ANN401
    ) -> None:
        self._contradiction_threshold = contradiction_threshold
        self._boundary_confidence_threshold = boundary_confidence_threshold
        self._source_quality_overrides = source_quality_overrides or {}
        self._retraction_penalty = retraction_penalty
        self._contradiction_detector = contradiction_detector or ContradictionDetector(
            threshold=contradiction_threshold
        )
        self._provenance_tracker = provenance_tracker

    # ------------------------------------------------------------------
    # Core: score a single claim
    # ------------------------------------------------------------------

    def score_claim(
        self,
        claim_text: str,
        sources: list[dict[str, Any]] | None = None,
        logprobs: dict[str, float] | None = None,
    ) -> ClaimConfidence:
        """Compute a composite confidence score for a claim.

        Args:
            claim_text: The claim to score.
            sources: List of source metadata dicts with keys like
                'quality' (SourceQuality str), 'retracted' (bool), etc.
            logprobs: Optional per-token log probabilities.

        Returns:
            A ClaimConfidence with per-axis breakdown.
        """
        if sources is None:
            sources = []

        source_quality = self._score_source_quality(sources)
        agreement = self._score_agreement(sources)
        model_conf = self._score_model_confidence(logprobs)
        density = self._score_evidence_density(len(sources))

        n_sources = sum(1 for s in sources if not self._is_contradictory(s))
        n_contra = sum(1 for s in sources if self._is_contradictory(s))

        confidence = 0.3 * source_quality + 0.3 * agreement + 0.2 * model_conf + 0.2 * density

        ci_lower = max(0.0, confidence - 0.1 * (1.0 - density))
        ci_upper = min(1.0, confidence + 0.1 * density)

        return ClaimConfidence(
            claim_text=claim_text,
            confidence_score=round(confidence, 4),
            source_quality_score=round(source_quality, 4),
            agreement_score=round(agreement, 4),
            model_confidence_score=round(model_conf, 4),
            evidence_density_score=round(density, 4),
            evidence_count=n_sources,
            contradictory_count=n_contra,
            confidence_interval=(round(ci_lower, 4), round(ci_upper, 4)),
        )

    def _score_source_quality(self, sources: list[dict[str, Any]]) -> float:
        if not sources:
            return 0.0
        total = 0.0
        for s in sources:
            raw = s.get("quality", SourceQuality.UNKNOWN.value)
            try:
                sq = SourceQuality(raw)
            except ValueError:
                sq = SourceQuality.UNKNOWN
            score = self._source_quality_overrides.get(
                sq.value, _SOURCE_QUALITY_SCORES.get(sq, 0.0)
            )
            if s.get("retracted", False):
                score = max(0.0, score + self._retraction_penalty)
            total += score
        return total / len(sources)

    def _score_agreement(self, sources: list[dict[str, Any]]) -> float:
        if not sources:
            return 0.0
        n_support = sum(1 for s in sources if not self._is_contradictory(s))
        return n_support / len(sources)

    def _is_contradictory(self, source: dict[str, Any]) -> bool:
        return source.get("contradicts", False)

    def _score_model_confidence(self, logprobs: dict[str, float] | None) -> float:
        if logprobs is None or not logprobs:
            return 0.5
        values = [v for v in logprobs.values() if v is not None]
        if not values:
            return 0.5
        mean_lp = sum(values) / len(values)
        return max(0.0, min(1.0, math.exp(mean_lp)))

    def _score_evidence_density(self, n_sources: int) -> float:
        return 1.0 - 1.0 / (1.0 + n_sources) if n_sources >= 0 else 0.0

    # ------------------------------------------------------------------
    # Knowledge boundary detection
    # ------------------------------------------------------------------

    def check_boundary(
        self,
        query: str,
        n_sources: int = 0,
    ) -> KnowledgeBoundary | None:
        """Check if a query lies outside the system's epistemic ken.

        Args:
            query: The research question or query text.
            n_sources: Number of relevant sources found.

        Returns:
            A KnowledgeBoundary if a boundary is detected, None otherwise.
        """
        if n_sources == 0:
            return KnowledgeBoundary(
                query=query,
                category="insufficient_literature",
                confidence=0.8,
                detail="No relevant sources found in available literature.",
            )

        lower = query.lower()
        for pattern in _UNANSWERABLE_PATTERNS:
            if pattern in lower:
                return KnowledgeBoundary(
                    query=query,
                    category="in_principle_unanswerable",
                    confidence=0.7,
                    detail=f"Query matches unanswerable pattern: '{pattern}'",
                )

        return None

    # ------------------------------------------------------------------
    # Model uncertainty extraction
    # ------------------------------------------------------------------

    def extract_uncertainty(
        self,
        chunks: list[Chunk] | None = None,
        logprobs: dict[str, float] | None = None,
    ) -> ModelUncertainty:
        """Extract model uncertainty signals from logprobs and chunk data.

        Args:
            chunks: Optional list of streamed chunks (for logprob aggregation).
            logprobs: Optional pre-aggregated per-token log probabilities.

        Returns:
            A ModelUncertainty with perplexity, entropy, and refusal flags.
        """
        if logprobs is None and chunks:
            aggregated: dict[str, float] = {}
            for c in chunks:
                if c.logprobs:
                    aggregated.update(c.logprobs)
            logprobs = aggregated if aggregated else None

        if logprobs is None or not logprobs:
            return ModelUncertainty(available=False)

        values = [v for v in logprobs.values() if v is not None]
        if not values:
            return ModelUncertainty(available=False)

        mean_lp = sum(values) / len(values)
        perplexity = math.exp(-mean_lp)
        entropy = -mean_lp / math.log(len(values)) if len(values) > 1 else 0.0

        refusal_text = " ".join(logprobs.keys())
        refusal_detected = any(p in refusal_text.lower() for p in _REFUSAL_PATTERNS)
        refusal_match = ""
        if refusal_detected:
            for p in _REFUSAL_PATTERNS:
                if p in refusal_text.lower():
                    refusal_match = p
                    break

        return ModelUncertainty(
            available=True,
            mean_logprob=round(mean_lp, 6),
            perplexity=round(perplexity, 4),
            entropy=round(entropy, 4),
            refusal_detected=refusal_detected,
            refusal_pattern=refusal_match,
        )

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def build_report(
        self,
        claims: list[ClaimConfidence],
        query: str = "",
        chunks: list[Chunk] | None = None,
    ) -> UncertaintyReport:
        """Build a complete uncertainty report for a set of claims.

        Args:
            claims: Scored claims to include.
            query: Original query for boundary detection.
            chunks: Optional chunks for model uncertainty extraction.

        Returns:
            An UncertaintyReport with contradictions, boundaries, and
            model uncertainty.
        """
        contradictions = self._contradiction_detector.detect(claims)
        boundary = self.check_boundary(query, len(claims)) if query else None
        model_uncertainty = self.extract_uncertainty(chunks) if chunks else None

        overall = self._compute_overall_confidence(claims, contradictions)

        return UncertaintyReport(
            claims=claims,
            contradictions=contradictions,
            boundaries=[boundary] if boundary else [],
            model_uncertainty=model_uncertainty,
            overall_confidence=round(overall, 4),
        )

    def _compute_overall_confidence(
        self,
        claims: list[ClaimConfidence],
        contradictions: list,
    ) -> float:
        if not claims:
            return 0.0
        mean = sum(c.confidence_score for c in claims) / len(claims)
        penalty = len(contradictions) * 0.05
        return max(0.0, mean - penalty)

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def format_report(self, report: UncertaintyReport) -> str:
        """Format an uncertainty report as human-readable text.

        Args:
            report: The report to format.

        Returns:
            Formatted string with confidence bars and indicators.
        """
        lines: list[str] = []

        overall = report.overall_confidence
        bar = self._confidence_bar(overall)
        lines.append(f"[Confidence: {bar} {overall:.0%}]")

        if report.claims:
            lines.append(f"Claims: {len(report.claims)}")
            n_support = sum(1 for c in report.claims if c.confidence_score >= 0.5)
            n_weak = len(report.claims) - n_support
            lines.append(f"  High confidence: {n_support}, Low confidence: {n_weak}")

        if report.contradictions:
            lines.append(f"[⚠ Contradictions: {len(report.contradictions)} detected]")
            for i, cd in enumerate(report.contradictions[:3]):
                lines.append(
                    f"  {i + 1}. {cd.contradiction_type.value} (severity: {cd.severity:.2f})"
                )

        if report.boundaries:
            for b in report.boundaries:
                lines.append(f"[BOUNDARY] {b.category}: {b.detail}")

        if report.model_uncertainty and report.model_uncertainty.available:
            mu = report.model_uncertainty
            lines.append(f"Model perplexity: {mu.perplexity:.2f}")

        return "\n".join(lines)

    @staticmethod
    def _confidence_bar(score: float, width: int = 10) -> str:
        filled = round(score * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    # ------------------------------------------------------------------
    # Mandatory disclosure
    # ------------------------------------------------------------------

    def disclose(
        self,
        claim_text: str,
        sources: list[dict[str, Any]] | None = None,
        logprobs: dict[str, float] | None = None,
    ) -> DisclosedClaim:
        """Wrap a claim with mandatory uncertainty disclosure.

        Args:
            claim_text: The generated claim.
            sources: Optional source metadata for scoring.
            logprobs: Optional model logprobs.

        Returns:
            A DisclosedClaim with confidence and disclosure text.
        """
        confidence = self.score_claim(claim_text, sources, logprobs)
        bar = self._confidence_bar(confidence.confidence_score)
        pct = f"{confidence.confidence_score:.0%}"
        disclosure = (
            f"[Confidence: {bar} {pct} | "
            f"Sources: {confidence.evidence_count} supporting, "
            f"{confidence.contradictory_count} contradicting]"
        )

        if confidence.confidence_score < 0.3:
            import contextlib

            with contextlib.suppress(Exception):
                if self._provenance_tracker is not None:
                    self._provenance_tracker.track(
                        action_type="low_confidence_claim",
                        params={
                            "claim": claim_text[:200],
                            "confidence": confidence.confidence_score,
                        },
                    )

        return DisclosedClaim(
            claim=claim_text,
            confidence=confidence,
            disclosure=disclosure,
        )

    def require_confidence(self, claim_text: str, min_confidence: float = 0.3) -> str:
        """Raise if a claim falls below the minimum confidence threshold.

        Args:
            claim_text: The claim to validate.
            min_confidence: Minimum acceptable confidence (0-1).

        Returns:
            The disclosure string if confidence meets the threshold.

        Raises:
            ValidationError: If confidence is below the minimum.
        """
        disclosed = self.disclose(claim_text)
        if disclosed.confidence.confidence_score < min_confidence:
            raise ValidationError(
                message=(
                    f"Claim confidence {disclosed.confidence.confidence_score:.2f} "
                    f"below minimum {min_confidence:.2f}. "
                    f"Disclosure: {disclosed.disclosure}"
                ),
                source="uncertainty.require_confidence",
                error_code=ErrorCode.UNCERTAINTY_INSUFFICIENT,
            )
        return disclosed.disclosure

    def score_sources_batch(
        self,
        sources: list[dict[str, Any]],
    ) -> list[float]:
        """Score a batch of sources by their quality metadata.

        Args:
            sources: List of source metadata dicts.

        Returns:
            List of quality scores (0-1) for each source.
        """
        return [self._score_single_source(s) for s in sources]

    def _score_single_source(self, source: dict[str, Any]) -> float:
        raw = source.get("quality", SourceQuality.UNKNOWN.value)
        try:
            sq = SourceQuality(raw)
        except ValueError:
            sq = SourceQuality.UNKNOWN
        score = self._source_quality_overrides.get(sq.value, _SOURCE_QUALITY_SCORES.get(sq, 0.0))
        if source.get("retracted", False):
            score = max(0.0, score + self._retraction_penalty)
        return round(score, 4)
