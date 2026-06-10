from __future__ import annotations

from typing import Any

from openscire.references.gap.models import GapSeverity, GapType, LiteratureGap
from openscire.references.models import ReferenceItem


class CoverageGapDetector:
    """Detects subtopics with insufficient source coverage."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_sources = config.get("gap_min_sources", 2)
        self.min_papers = config.get("gap_min_papers", 5)

    def detect(
        self,
        topic: str,
        subtopics: dict[str, list[ReferenceItem]],
    ) -> list[LiteratureGap]:
        gaps: list[LiteratureGap] = []
        for subtopic, items in subtopics.items():
            if not items:
                continue
            sources: set[str] = set()
            for ref in items:
                sources.add(ref.source.value)
            n_sources = len(sources)
            n_papers = len(items)
            if n_sources < self.min_sources:
                missing = [
                    s
                    for s in ("pubmed", "semantic_scholar", "openalex", "arxiv")
                    if s not in sources
                ]
                gaps.append(
                    LiteratureGap(
                        gap_type=GapType.coverage,
                        severity=GapSeverity.high,
                        topic=subtopic,
                        description=(
                            f"Subtopic '{subtopic}' under '{topic}' has only {n_sources} source(s) "
                            f"(min {self.min_sources} required). Sources found: {', '.join(sorted(sources)) or 'none'}."
                        ),
                        recommendation=(
                            f"Search {', '.join(missing)} for '{subtopic}' to broaden evidence base."
                        ),
                        affected_count=n_papers,
                        details={
                            "sources_found": sorted(sources),
                            "missing_sources": missing,
                            "n_papers": n_papers,
                        },
                    )
                )
            elif n_papers < self.min_papers:
                gaps.append(
                    LiteratureGap(
                        gap_type=GapType.coverage,
                        severity=GapSeverity.medium,
                        topic=subtopic,
                        description=(
                            f"Subtopic '{subtopic}' under '{topic}' has only {n_papers} paper(s) "
                            f"(min {self.min_papers} recommended)."
                        ),
                        recommendation=(
                            f"Search for more papers on '{subtopic}' to strengthen coverage."
                        ),
                        affected_count=n_papers,
                        details={"sources_found": sorted(sources), "n_papers": n_papers},
                    )
                )
        return gaps

    @staticmethod
    def group_by_keywords(items: list[ReferenceItem]) -> dict[str, list[ReferenceItem]]:
        groups: dict[str, list[ReferenceItem]] = {}
        for item in items:
            keywords = item.keywords or ["uncategorized"]
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower not in groups:
                    groups[kw_lower] = []
                groups[kw_lower].append(item)
        return groups
