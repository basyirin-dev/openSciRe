# SPDX-License-Identifier: Apache-2.0

"""Tests for CitationGraphAnalyzer."""

import networkx as nx
import pytest
from openscire.references.graph.analyzer import CitationGraphAnalyzer
from openscire.references.graph.models import (
    CitationGraphReport,
    CitationTimeline,
    ClusterReport,
    DecayReport,
    GraphExport,
    InfluenceReport,
)
from openscire.references.models import (
    CitationGraphEntry,
    ReferenceItem,
    ReferenceSource,
)


def _make_ref(
    pid: str, title: str = "", year: int | None = None, extra: dict | None = None
) -> ReferenceItem:
    return ReferenceItem(
        id=pid,
        source=ReferenceSource.openalex,
        title=title,
        year=year,
        extra=extra or {},
    )


class TestBuild:
    def test_build_delegates_to_builder(self):
        analyzer = CitationGraphAnalyzer()
        r1 = _make_ref("W001", "A", 2020, {"referenced_works": ["https://api.openalex.org/W002"]})
        r2 = _make_ref("W002", "B", 2019)
        G = analyzer.build_graph([r1, r2])
        assert G.number_of_nodes() == 2
        assert G.has_edge("W001", "W002")


class TestAnalyze:
    def test_analyze_returns_report(self):
        analyzer = CitationGraphAnalyzer()
        refs = [
            _make_ref("W001", "A", 2020),
            _make_ref("W002", "B", 2021),
        ]
        report = analyzer.analyze(refs)
        assert isinstance(report, CitationGraphReport)
        assert report.node_count == 2
        assert report.edge_count == 0

    def test_report_contains_all_sections(self):
        analyzer = CitationGraphAnalyzer()
        refs = [
            _make_ref("W001", "A", 2020, {"referenced_works": ["https://api.openalex.org/W002"]}),
            _make_ref("W002", "B", 2019),
        ]
        report = analyzer.analyze(refs)
        assert isinstance(report.influence, InfluenceReport)
        assert isinstance(report.timelines, list)
        assert isinstance(report.decay, DecayReport)
        assert isinstance(report.clusters, ClusterReport)

    def test_empty_refs(self):
        analyzer = CitationGraphAnalyzer()
        report = analyzer.analyze([])
        assert report.node_count == 0
        assert report.edge_count == 0

    def test_analyze_graph_accepts_prebuilt(self):
        analyzer = CitationGraphAnalyzer()
        G = nx.DiGraph()
        G.add_node("W001", ref=_make_ref("W001", "A"))
        G.add_node("W002", ref=_make_ref("W002", "B"))
        G.add_edge("W001", "W002")
        report = analyzer.analyze_graph(G)
        assert report.node_count == 2
        assert report.edge_count == 1


class TestDelegation:
    def test_export_delegates(self):
        analyzer = CitationGraphAnalyzer()
        G = nx.DiGraph()
        G.add_node("W001")
        export = analyzer.export(G, "d3")
        assert isinstance(export, GraphExport)
        assert export.format == "d3"

    def test_influence_delegates(self):
        analyzer = CitationGraphAnalyzer()
        G = nx.DiGraph()
        G.add_node("W001")
        report = analyzer.influence(G)
        assert isinstance(report, InfluenceReport)

    def test_influence_ego_delegates(self):
        analyzer = CitationGraphAnalyzer()
        G = nx.DiGraph()
        G.add_node("center")
        report = analyzer.influence_ego(G, "center")
        assert isinstance(report, InfluenceReport)

    def test_timeline_delegates(self):
        analyzer = CitationGraphAnalyzer()
        G = nx.DiGraph()
        G.add_node("W001", ref=_make_ref("W001", "Test"))
        timelines = analyzer.timeline(G)
        assert all(isinstance(t, CitationTimeline) for t in timelines)

    def test_decay_delegates(self):
        analyzer = CitationGraphAnalyzer()
        G = nx.DiGraph()
        G.add_node("W001", ref=_make_ref("W001", "Test"))
        report = analyzer.detect_decay(G)
        assert isinstance(report, DecayReport)

    def test_cocitation_delegates(self):
        analyzer = CitationGraphAnalyzer()
        G = nx.DiGraph()
        G.add_node("W001")
        report = analyzer.co_citation_clustering(G)
        assert isinstance(report, ClusterReport)

    def test_bibliographic_delegates(self):
        analyzer = CitationGraphAnalyzer()
        G = nx.DiGraph()
        G.add_node("W001")
        report = analyzer.bibliographic_coupling(G)
        assert isinstance(report, ClusterReport)


class TestTraverse:
    @pytest.mark.asyncio
    async def test_no_clients_returns_seed_graph(self):
        analyzer = CitationGraphAnalyzer()
        ref = _make_ref("W001", "Seed")
        G = await analyzer.traverse([ref], depth=1)
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0

    @pytest.mark.asyncio
    async def test_with_mock_client(self):
        class MockSS:
            async def get_citations(self, pid):
                citing = _make_ref("W002", "Citing Paper", 2021)
                cited = _make_ref("W001", "Original", 2020)
                return [CitationGraphEntry(citing_paper=citing, cited_paper=cited)]

            async def get_references(self, pid):
                return []

        analyzer = CitationGraphAnalyzer(bridge_clients={"semantic_scholar": MockSS()})
        seed = _make_ref("W001", "Original", 2020)
        G = await analyzer.traverse([seed], depth=1)
        assert G.number_of_nodes() >= 2
        assert G.has_edge("W002", "W001")

    @pytest.mark.asyncio
    async def test_depth_0_no_traversal(self):
        analyzer = CitationGraphAnalyzer()
        ref = _make_ref("W001", "Seed")
        G = await analyzer.traverse([ref], depth=0)
        assert G.number_of_nodes() == 1

    @pytest.mark.asyncio
    async def test_deduplicates_nodes_across_hops(self):
        class MockSS:
            async def get_citations(self, pid):
                return []

            async def get_references(self, pid):
                return []

        analyzer = CitationGraphAnalyzer(bridge_clients={"semantic_scholar": MockSS()})
        ref = _make_ref("W001", "Seed")
        G = await analyzer.traverse([ref, ref], depth=1)
        assert G.number_of_nodes() == 1
