# SPDX-License-Identifier: Apache-2.0

"""TemporalAnalyzer — citation timeline extraction and decay detection."""

from typing import Any

import networkx as nx

from openscire.references.graph.models import (
    CitationTimeline,
    DecayReport,
    DecayResult,
    YearCount,
)


class TemporalAnalyzer:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.decay_threshold = self.config.get("decay_threshold", 0.7)
        self.decay_window = self.config.get("decay_window", 3)
        self.min_peak_citations = self.config.get("min_peak_citations", 3)

    def timeline(self, graph: nx.DiGraph) -> list[CitationTimeline]:
        timelines: list[CitationTimeline] = []
        for node_id in graph.nodes:
            ref = graph.nodes[node_id].get("ref")
            if ref is None:
                timelines.append(CitationTimeline(paper_id=node_id))
                continue
            counts_by_year = ref.extra.get("counts_by_year", [])
            if not isinstance(counts_by_year, list):
                counts_by_year = []
            yearly_counts = []
            for entry in counts_by_year:
                year = entry.get("year", 0) if isinstance(entry, dict) else 0
                count = entry.get("cited_by_count", 0) if isinstance(entry, dict) else 0
                yearly_counts.append(YearCount(year=year, count=count))
            total = sum(yc.count for yc in yearly_counts)
            timelines.append(
                CitationTimeline(
                    paper_id=node_id,
                    title=ref.title,
                    yearly_counts=yearly_counts,
                    total_citations=total,
                )
            )
        return timelines

    def detect_decay(self, graph: nx.DiGraph, current_year: int = 2026) -> DecayReport:
        results: list[DecayResult] = []
        for node_id in graph.nodes:
            ref = graph.nodes[node_id].get("ref")
            if ref is None:
                results.append(DecayResult(paper_id=node_id, reason="no reference data"))
                continue
            counts_by_year = ref.extra.get("counts_by_year", [])
            if not isinstance(counts_by_year, list) or len(counts_by_year) < 2:
                results.append(
                    DecayResult(paper_id=node_id, title=ref.title, reason="insufficient data")
                )
                continue
            yearly = {}
            for entry in counts_by_year:
                if isinstance(entry, dict):
                    y = entry.get("year", 0)
                    c = entry.get("cited_by_count", 0)
                    yearly[y] = c
            if len(yearly) < 2:
                results.append(
                    DecayResult(paper_id=node_id, title=ref.title, reason="insufficient data")
                )
                continue
            peak_year = max(yearly, key=yearly.get)
            peak_velocity = yearly[peak_year]
            if peak_velocity < self.min_peak_citations:
                results.append(
                    DecayResult(
                        paper_id=node_id,
                        title=ref.title,
                        reason=(
                            f"peak citations ({peak_velocity}) "
                            f"below minimum ({self.min_peak_citations})"
                        ),
                    )
                )
                continue
            window_start = current_year - self.decay_window
            recent_years = [y for y in yearly if y >= window_start]
            if not recent_years:
                recent_velocity = 0.0
            else:
                recent_velocity = sum(yearly[y] for y in recent_years) / len(recent_years)
            decay_score = 1.0 - (recent_velocity / peak_velocity) if peak_velocity > 0 else 0.0
            is_decayed = decay_score > self.decay_threshold
            reason = ""
            if is_decayed:
                reason = (
                    f"recent velocity ({recent_velocity:.1f}) vs peak "
                    f"({peak_velocity:.1f}, {peak_year}) yields decay score "
                    f"{decay_score:.2f} > threshold {self.decay_threshold}"
                )
            results.append(
                DecayResult(
                    paper_id=node_id,
                    title=ref.title,
                    is_decayed=is_decayed,
                    decay_score=round(decay_score, 4),
                    peak_year=peak_year,
                    peak_velocity=float(peak_velocity),
                    recent_velocity=round(recent_velocity, 4),
                    reason=reason,
                )
            )
        decayed = [r.paper_id for r in results if r.is_decayed]
        healthy = [r.paper_id for r in results if not r.is_decayed]
        return DecayReport(
            results=results,
            decayed_papers=decayed,
            healthy_papers=healthy,
            threshold=self.decay_threshold,
        )
