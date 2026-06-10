from __future__ import annotations

from typing import Any

from openscire.logging import get_logger
from openscire.references.gap.coverage import CoverageGapDetector
from openscire.references.gap.geography import GeographicGapDetector
from openscire.references.gap.methodology import MethodologicalMonocultureDetector
from openscire.references.gap.models import GapReport, LiteratureGap
from openscire.references.gap.temporal import TemporalGapDetector
from openscire.references.models import ReferenceItem

logger = get_logger("openscire.references.gap.analyzer")


class GapAnalyzer:
    """Orchestrates all gap detectors and produces a GapReport."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        provenance_tracker: Any = None,
    ) -> None:
        self.config = config or {}
        self._provenance_tracker = provenance_tracker
        self._coverage = CoverageGapDetector(self.config)
        self._methodology = MethodologicalMonocultureDetector(self.config)
        self._geography = GeographicGapDetector(self.config)
        self._temporal = TemporalGapDetector(self.config)

    def analyze(
        self,
        topic: str,
        references: list[ReferenceItem],
        subtopics: dict[str, list[ReferenceItem]] | None = None,
        country_map: dict[str, str] | None = None,
    ) -> GapReport:
        gaps: list[LiteratureGap] = []
        effective_subtopics = subtopics or CoverageGapDetector.group_by_keywords(references)
        gaps.extend(self._coverage.detect(topic, effective_subtopics))
        for subtopic_name, subtopic_items in effective_subtopics.items():
            gaps.extend(self._methodology.detect(subtopic_name, subtopic_items))
        gaps.extend(self._geography.detect(topic, references, country_map=country_map))
        gaps.extend(self._temporal.detect(topic, references))

        if self._provenance_tracker is not None:
            gap_counts: dict[str, int] = {}
            for g in gaps:
                gap_counts[g.gap_type.value] = gap_counts.get(g.gap_type.value, 0) + 1
            try:
                self._provenance_tracker.track(
                    action_type="gap_analysis",
                    params={
                        "topic": topic,
                        "total_references": len(references),
                        "total_gaps": len(gaps),
                        "gap_counts": gap_counts,
                    },
                )
            except Exception:
                logger.warning("Failed to record gap analysis provenance", exc_info=True)

        return GapReport(
            topic=topic,
            total_references=len(references),
            gaps=gaps,
            config=self.config,
        )

    def detect_coverage(
        self,
        topic: str,
        subtopics: dict[str, list[ReferenceItem]],
    ) -> list[LiteratureGap]:
        return self._coverage.detect(topic, subtopics)

    def detect_methodology(
        self,
        topic: str,
        items: list[ReferenceItem],
    ) -> list[LiteratureGap]:
        return self._methodology.detect(topic, items)

    def detect_geography(
        self,
        topic: str,
        items: list[ReferenceItem],
        country_map: dict[str, str] | None = None,
    ) -> list[LiteratureGap]:
        return self._geography.detect(topic, items, country_map=country_map)

    def detect_temporal(
        self,
        topic: str,
        items: list[ReferenceItem],
    ) -> list[LiteratureGap]:
        return self._temporal.detect(topic, items)
