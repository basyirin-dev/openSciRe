# SPDX-License-Identifier: Apache-2.0

"""Tests for ClusterEngine."""

import networkx as nx

from openscire.references.graph.clustering import ClusterEngine


class TestCoCitation:
    def setup_method(self):
        self.engine = ClusterEngine()

    def test_empty_graph(self):
        report = self.engine.co_citation_clustering(nx.DiGraph())
        assert report.clusters == []
        assert report.method == "co_citation"

    def test_no_cocitations(self):
        G = nx.DiGraph()
        G.add_node("W001", ref=None)
        G.add_node("W002", ref=None)
        G.add_edge("W002", "W001")
        report = self.engine.co_citation_clustering(G)
        assert len(report.clusters) == 0

    def test_single_cocitation_pair(self):
        G = nx.DiGraph()
        for n in ["citing", "A", "B"]:
            G.add_node(n, ref=None)
        G.add_edge("citing", "A")
        G.add_edge("citing", "B")
        report = self.engine.co_citation_clustering(G, min_co_citation=1)
        assert len(report.clusters) >= 1

    def test_min_co_citation_filter(self):
        G = nx.DiGraph()
        for n in ["C1", "C2", "A", "B"]:
            G.add_node(n, ref=None)
        G.add_edge("C1", "A")
        G.add_edge("C2", "A")
        G.add_edge("C2", "B")
        report = self.engine.co_citation_clustering(G, min_co_citation=2)
        assert len(report.clusters) == 0

    def test_co_citation_similarity_graph(self):
        G = nx.DiGraph()
        for n in ["C1", "C2", "X", "Y", "Z"]:
            G.add_node(n, ref=None)
        G.add_edge("C1", "X")
        G.add_edge("C1", "Y")
        G.add_edge("C2", "X")
        G.add_edge("C2", "Y")
        G.add_edge("C2", "Z")
        sim = self.engine.co_citation_similarity(G, min_co_citation=1)
        assert sim.has_edge("X", "Y")
        assert sim.has_edge("X", "Z")
        assert sim.has_edge("Y", "Z")
        assert sim.edges["X", "Y"]["weight"] == 2

    def test_no_edges(self):
        G = nx.DiGraph()
        G.add_node("W001", ref=None)
        G.add_node("W002", ref=None)
        report = self.engine.co_citation_clustering(G)
        assert report.clusters == []


class TestBibliographicCoupling:
    def setup_method(self):
        self.engine = ClusterEngine()

    def test_empty_graph(self):
        report = self.engine.bibliographic_coupling(nx.DiGraph())
        assert report.method == "bibliographic_coupling"

    def test_no_coupling(self):
        G = nx.DiGraph()
        for n in ["A", "B", "ref"]:
            G.add_node(n, ref=None)
        G.add_edge("A", "ref")
        G.add_edge("B", "ref")
        report = self.engine.bibliographic_coupling(G, min_coupling=2)
        assert len(report.clusters) == 0

    def test_single_coupling_pair(self):
        G = nx.DiGraph()
        for n in ["A", "B", "R1", "R2"]:
            G.add_node(n, ref=None)
        G.add_edge("A", "R1")
        G.add_edge("A", "R2")
        G.add_edge("B", "R1")
        G.add_edge("B", "R2")
        report = self.engine.bibliographic_coupling(G, min_coupling=1)
        assert len(report.clusters) >= 1

    def test_coupling_similarity_graph(self):
        G = nx.DiGraph()
        for n in ["A", "B", "C", "R1", "R2", "R3"]:
            G.add_node(n, ref=None)
        G.add_edge("A", "R1")
        G.add_edge("A", "R2")
        G.add_edge("B", "R1")
        G.add_edge("B", "R2")
        G.add_edge("B", "R3")
        G.add_edge("C", "R3")
        sim = self.engine.bibliographic_similarity(G, min_coupling=1)
        assert sim.has_edge("A", "B")
        assert sim.has_edge("B", "C")
        assert not sim.has_edge("A", "C")
        assert sim.edges["A", "B"]["weight"] == 2

    def test_isolated_nodes_excluded(self):
        G = nx.DiGraph()
        G.add_node("isolated", ref=None)
        G.add_node("A", ref=None)
        G.add_node("B", ref=None)
        G.add_node("R", ref=None)
        G.add_edge("A", "R")
        G.add_edge("B", "R")
        report = self.engine.bibliographic_coupling(G, min_coupling=1)
        assert len(report.clusters) >= 1
        all_ids = set()
        for cl in report.clusters:
            all_ids.update(cl.paper_ids)
        assert "isolated" not in all_ids
