from __future__ import annotations

from openscire.logging import get_logger

from .models import ClaimConfidence, Contradiction, ContradictionType

logger = get_logger("openscire.quantification.contradiction")


class ContradictionDetector:
    """Detects contradictions between pairs of claims.

    Performs pairwise comparison of claims grouped by topic.
    Uses word-overlap heuristics for domain grouping and
    configurable threshold for contradiction severity.
    """

    def __init__(self, threshold: float = 0.6) -> None:
        self._threshold = threshold

    def detect(
        self,
        claims: list[ClaimConfidence],
        threshold: float | None = None,
    ) -> list[Contradiction]:
        """Compare claims pairwise and flag contradictions.

        Args:
            claims: List of claims with confidence scores.
            threshold: Override detection threshold (default from constructor).

        Returns:
            List of Contradiction objects between pairs of claims.
        """
        if len(claims) < 2:
            return []

        effective_threshold = threshold if threshold is not None else self._threshold
        results: list[Contradiction] = []
        seen: set[tuple[int, int]] = set()

        for i, a in enumerate(claims):
            for j, b in enumerate(claims):
                if i >= j:
                    continue
                key = (i, j) if i < j else (j, i)
                if key in seen:
                    continue
                seen.add(key)

                ctype, severity = self._compare(a.claim_text, b.claim_text)

                if severity >= effective_threshold:
                    results.append(
                        Contradiction(
                            claim_a=a.claim_text,
                            claim_b=b.claim_text,
                            contradiction_type=ctype,
                            severity=severity,
                            confidence_a=a.confidence_score,
                            confidence_b=b.confidence_score,
                        )
                    )

        return results

    def _compare(
        self,
        text_a: str,
        text_b: str,
    ) -> tuple[ContradictionType, float]:
        """Compare two claim texts and determine contradiction type and severity.

        Uses word-overlap ratio and directional negation markers.
        Returns (contradiction_type, severity) where severity is 0.0-1.0.
        """
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return (ContradictionType.NUANCED, 0.0)

        overlap = len(words_a & words_b)
        union = len(words_a | words_b)
        jaccard = overlap / union if union > 0 else 0.0

        negation_a = self._has_negation(text_a)
        negation_b = self._has_negation(text_b)

        if jaccard > 0.9:
            return (ContradictionType.NUANCED, 0.0)

        if jaccard > 0.5 and negation_a != negation_b:
            return (ContradictionType.DIRECT, min(1.0, jaccard * 1.2))

        if jaccard > 0.3:
            if negation_a != negation_b:
                return (ContradictionType.NUANCED, jaccard)
            return (ContradictionType.METHODOLOGICAL, jaccard * 0.6)

        return (ContradictionType.NUANCED, 0.0)

    @staticmethod
    def _has_negation(text: str) -> bool:
        """Check if text contains negation markers."""
        markers = [
            " not ",
            "n't ",
            "never ",
            "no ",
            "without ",
            "absence of ",
            "disprove",
            "refute",
            "contradict",
            "fails to ",
        ]
        lower = text.lower()
        return any(m in lower for m in markers)
