from __future__ import annotations

import math
import re
from typing import Any

from openscire.curation.models import SourceQualityScore
from openscire.models.models import ReproducibilityStatus
from openscire.references.models import ReferenceItem


_METHOD_PATTERNS: dict[str, list[str]] = {
    "meta-analysis": [r"\bmeta-analysis\b", r"\bmeta analysis\b", r"\bsystematic review\b"],
    "clinical trial": [r"\bclinical trial\b", r"\brandomized\b", r"\bphase [iiv]+\b"],
    "observational": [r"\bobservational\b", r"\bcohort\b", r"\bcase-control\b"],
    "in vivo": [r"\bin vivo\b", r"\banimal model\b", r"\bmurine\b"],
    "in vitro": [r"\bin vitro\b", r"\bcell culture\b", r"\bcell line\b"],
    "case study": [r"\bcase study\b", r"\bcase report\b"],
}

_METHODOLOGY_ORDER: list[str] = [
    "meta-analysis",
    "clinical trial",
    "observational",
    "in vivo",
    "in vitro",
    "case study",
]


class SourceQualityScorer:
    """Scores a source on multiple evidence-quality dimensions."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.weights = config.get("quality_weights", {
            "methodology": 0.30,
            "replication": 0.25,
            "citation": 0.15,
            "recency": 0.30,
        })

    def score(self, source: ReferenceItem) -> SourceQualityScore:
        methodology = self._score_methodology(source)
        replication = self._score_replication(source)
        citation_val = self._score_citation(source)
        recency = self._score_recency(source)
        overall = (
            methodology * self.weights["methodology"]
            + replication * self.weights["replication"]
            + citation_val * self.weights["citation"]
            + recency * self.weights["recency"]
        )
        return SourceQualityScore(
            source_id=source.id,
            overall_score=round(overall, 4),
            methodology_score=methodology,
            replication_score=replication,
            citation_score=citation_val,
            recency_score=recency,
        )

    def _score_methodology(self, source: ReferenceItem) -> float:
        text = f"{source.title} {source.abstract}".lower()
        for rank, method in enumerate(_METHODOLOGY_ORDER):
            patterns = _METHOD_PATTERNS.get(method, [])
            for pat in patterns:
                if re.search(pat, text):
                    return 1.0 - (rank / len(_METHODOLOGY_ORDER))
        return 0.1

    def _score_replication(self, source: ReferenceItem) -> float:
        status = source.extra.get("reproducibility_status", "")
        if status == ReproducibilityStatus.reproduced:
            return 1.0
        if status == ReproducibilityStatus.failed_to_reproduce:
            return 0.3
        if status == ReproducibilityStatus.pending:
            return 0.5
        return 0.5

    def _score_citation(self, source: ReferenceItem) -> float:
        citation_count = source.extra.get("citation_count", 0)
        if isinstance(citation_count, str):
            try:
                citation_count = int(citation_count)
            except (ValueError, TypeError):
                citation_count = 0
        if not isinstance(citation_count, (int, float)) or citation_count < 0:
            citation_count = 0
        if citation_count == 0:
            return 0.0
        return round(min(math.log10(citation_count + 1) / 3.0, 1.0), 4)

    def _score_recency(self, source: ReferenceItem) -> float:
        year = source.year
        if year is None:
            return 0.3
        current = 2026
        age = current - year
        if age <= 1:
            return 1.0
        if age >= 30:
            return 0.1
        return round(1.0 - (age / 30.0), 4)


class ConfidenceWeightedRanker:
    """Ranks scored sources by overall quality score descending."""

    def rank(self, scores: list[SourceQualityScore]) -> list[SourceQualityScore]:
        return sorted(scores, key=lambda s: s.overall_score, reverse=True)
