# SPDX-License-Identifier: Apache-2.0

"""CitationGraphAnalyzer — orchestrates citation graph construction and analysis."""

from typing import Any

import networkx as nx

from openscire.logging import get_logger
from openscire.references.graph.builder import CitationGraphBuilder
from openscire.references.graph.clustering import ClusterEngine
from openscire.references.graph.export import GraphExporter
from openscire.references.graph.influence import InfluenceScorer
from openscire.references.graph.models import (
    CitationGraphReport,
    GraphExport,
    InfluenceReport,
)
from openscire.references.graph.temporal import TemporalAnalyzer
from openscire.references.models import CitationGraphEntry, ReferenceItem

logger = get_logger("openscire.references.graph.analyzer")


class CitationGraphAnalyzer:
    def __init__(  # noqa: ANN204
        self,
        bridge_clients: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        provenance_tracker: Any = None,
    ):
        self.clients = bridge_clients or {}
        self.config = config or {}
        self._provenance_tracker = provenance_tracker
        self.builder = CitationGraphBuilder()
        self.scorer = InfluenceScorer()
        self.temporal = TemporalAnalyzer(self.config.get("temporal"))
        self.clustering = ClusterEngine(self.config.get("clustering"))
        self.exporter = GraphExporter()

    def build_graph(self, refs: list[ReferenceItem]) -> nx.DiGraph:
        graph = self.builder.build(refs)
        if self._provenance_tracker is not None:
            try:
                self._provenance_tracker.track(
                    action_type="citation_graph_build",
                    params={
                        "n_refs": len(refs),
                        "n_nodes": graph.number_of_nodes(),
                        "n_edges": graph.number_of_edges(),
                    },
                )
            except Exception:
                logger.warning("Failed to record graph build provenance", exc_info=True)
        return graph

    def build_graph_from_entries(
        self,
        entries: list[CitationGraphEntry],
        ref_lookup: dict[str, ReferenceItem],
    ) -> nx.DiGraph:
        graph = self.builder.build_from_entries(entries, ref_lookup)
        if self._provenance_tracker is not None:
            try:
                self._provenance_tracker.track(
                    action_type="citation_graph_build_from_entries",
                    params={
                        "n_entries": len(entries),
                        "n_nodes": graph.number_of_nodes(),
                        "n_edges": graph.number_of_edges(),
                    },
                )
            except Exception:
                logger.warning("Failed to record graph build provenance", exc_info=True)
        return graph

    def analyze(self, refs: list[ReferenceItem]) -> CitationGraphReport:
        graph = self.build_graph(refs)
        return self._report_from_graph(graph)

    def analyze_graph(self, graph: nx.DiGraph) -> CitationGraphReport:
        return self._report_from_graph(graph)

    def _report_from_graph(self, graph: nx.DiGraph) -> CitationGraphReport:
        influence = self.scorer.score(graph)
        timelines = self.temporal.timeline(graph)
        decay = self.temporal.detect_decay(graph)
        clusters = self.clustering.co_citation_clustering(graph)
        if self._provenance_tracker is not None:
            try:
                self._provenance_tracker.track(
                    action_type="citation_graph_analysis",
                    params={
                        "node_count": graph.number_of_nodes(),
                        "edge_count": graph.number_of_edges(),
                        "n_influential_nodes": len(influence.results) if influence.results else 0,
                        "decay_detected": decay.detected if decay else False,
                        "n_clusters": len(clusters) if clusters else 0,
                    },
                )
            except Exception:
                logger.warning("Failed to record graph analysis provenance", exc_info=True)
        return CitationGraphReport(
            influence=influence,
            timelines=timelines,
            decay=decay,
            clusters=clusters,
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
        )

    async def traverse(
        self,
        seed_refs: list[ReferenceItem],
        depth: int = 2,
        direction: str = "both",
    ) -> nx.DiGraph:
        graph = nx.DiGraph()
        all_seen: set[str] = set()
        for ref in seed_refs:
            if ref.id not in all_seen:
                all_seen.add(ref.id)
                graph = _merge_ref(graph, ref)
        frontier: dict[str, ReferenceItem] = {r.id: r for r in seed_refs if r.id in all_seen}
        for _ in range(depth):
            if not frontier:
                break
            batch = list(frontier.values())
            frontier.clear()
            for ref in batch:
                entries = await self._fetch_citation_edges(ref.id, direction)
                for entry in entries:
                    new_refs = _collect_new_refs(entry, all_seen)
                    for nr in new_refs:
                        all_seen.add(nr.id)
                        frontier[nr.id] = nr
                    graph = self._apply_entry(graph, entry)
        return graph

    async def _fetch_citation_edges(
        self,
        paper_id: str,
        direction: str,
    ) -> list[CitationGraphEntry]:
        entries: list[CitationGraphEntry] = []
        if "semantic_scholar" in self.clients and direction in ("citations", "both"):
            try:
                cites = await self.clients["semantic_scholar"].get_citations(paper_id)
                entries.extend(cites)
            except Exception:
                pass
        if "semantic_scholar" in self.clients and direction in ("references", "both"):
            try:
                refs = await self.clients["semantic_scholar"].get_references(paper_id)
                entries.extend(refs)
            except Exception:
                pass
        return entries

    def _apply_entry(
        self,
        graph: nx.DiGraph,
        entry: CitationGraphEntry,
    ) -> nx.DiGraph:
        if entry.citing_paper:
            graph = _merge_ref(graph, entry.citing_paper)
        if entry.cited_paper:
            graph = _merge_ref(graph, entry.cited_paper)
        if entry.citing_paper and entry.cited_paper:
            graph.add_edge(
                entry.citing_paper.id,
                entry.cited_paper.id,
                contexts=entry.contexts,
                is_influential=entry.is_influential,
            )
        return graph

    def export(self, graph: nx.DiGraph, fmt: str = "d3") -> GraphExport:  # noqa: ANN401
        return self.exporter.export(graph, fmt)

    def influence(
        self, graph: nx.DiGraph, **kwargs: object
    ) -> InfluenceReport:
        return self.scorer.score(graph, **kwargs)

    def influence_ego(
        self, graph: nx.DiGraph, node_id: str, **kwargs: object
    ) -> InfluenceReport:
        return self.scorer.score_ego(graph, node_id, **kwargs)

    def timeline(
        self, graph: nx.DiGraph
    ) -> list:
        return self.temporal.timeline(graph)

    def detect_decay(
        self, graph: nx.DiGraph
    ) -> object:
        return self.temporal.detect_decay(graph)

    def co_citation_clustering(
        self, graph: nx.DiGraph, **kwargs: object
    ) -> object:
        return self.clustering.co_citation_clustering(graph, **kwargs)

    def bibliographic_coupling(
        self, graph: nx.DiGraph, **kwargs: object
    ) -> object:
        return self.clustering.bibliographic_coupling(graph, **kwargs)


def _merge_ref(graph: nx.DiGraph, ref: ReferenceItem) -> nx.DiGraph:
    if ref.id not in graph:
        graph.add_node(ref.id, ref=ref)
    return graph


def _collect_new_refs(
    entry: CitationGraphEntry,
    seen: set[str],
) -> list[ReferenceItem]:
    result: list[ReferenceItem] = []
    if entry.citing_paper and entry.citing_paper.id not in seen:
        result.append(entry.citing_paper)
    if entry.cited_paper and entry.cited_paper.id not in seen:
        result.append(entry.cited_paper)
    return result
