from __future__ import annotations

from typing import Any

from openscire.references.gap.models import GapSeverity, GapType, LiteratureGap
from openscire.references.models import ReferenceItem


class TemporalGapDetector:
    """Detects gaps in temporal coverage."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_gap_years = config.get("gap_min_gap_years", 2)
        self.recency_years = config.get("gap_recency_years", 3)

    def detect(
        self,
        topic: str,
        items: list[ReferenceItem],
    ) -> list[LiteratureGap]:
        gaps: list[LiteratureGap] = []
        years: list[int] = sorted(ref.year for ref in items if ref.year is not None)
        if not years:
            return gaps
        if len(years) < 2:
            return gaps
        gaps_in_timeline: list[tuple[int, int]] = []
        for i in range(1, len(years)):
            gap = years[i] - years[i - 1]
            if gap > self.min_gap_years:
                gaps_in_timeline.append((years[i - 1], years[i]))
        for start, end in gaps_in_timeline:
            gap_duration = end - start
            severity = GapSeverity.high if gap_duration >= 5 else GapSeverity.medium
            gaps.append(
                LiteratureGap(
                    gap_type=GapType.temporal,
                    severity=severity,
                    topic=topic,
                    description=(
                        f"No studies found for '{topic}' between {start} and {end} "
                        f"({gap_duration}-year gap)."
                    ),
                    recommendation=(
                        f"Search for studies on '{topic}' published {start}–{end} "
                        "to fill the temporal gap."
                    ),
                    affected_count=0,
                    details={
                        "gap_start": start,
                        "gap_end": end,
                        "gap_duration": gap_duration,
                        "min_gap_years": self.min_gap_years,
                    },
                )
            )
        latest_year = years[-1]
        current_year = 2026
        recency_gap = current_year - latest_year
        if recency_gap >= self.recency_years and len(years) > 1:
            severity = GapSeverity.high if recency_gap >= 5 else GapSeverity.medium
            gaps.append(
                LiteratureGap(
                    gap_type=GapType.temporal,
                    severity=severity,
                    topic=topic,
                    description=(
                        f"No recent studies on '{topic}' since {latest_year} "
                        f"({recency_gap}-year gap from current year {current_year})."
                    ),
                    recommendation=(
                        f"Search for recent literature on '{topic}' from {latest_year} onward."
                    ),
                    affected_count=0,
                    details={
                        "latest_year": latest_year,
                        "recency_gap": recency_gap,
                        "current_year": current_year,
                    },
                )
            )
        return gaps
