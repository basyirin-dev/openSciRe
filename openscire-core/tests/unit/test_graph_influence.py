# SPDX-License-Identifier: Apache-2.0

"""Tests for InfluenceScorer."""

import networkx as nx

from openscire.references.graph.influence import InfluenceScorer


class TestPageRank:
    def test_empty_graph_returns_empty_report(self):
        G = nx.DiGraph()
        report = InfluenceScorer.score(G)
        assert report.results == []
        assert report.damping_factor == 0.85

    def test_single_node(self):
        G = nx.DiGraph()
        G.add_node("W001", ref=None)
        report = InfluenceScorer.score(G)
        assert len(report.results) == 1
        assert report.results[0].paper_id == "W001"
        assert report.results[0].score == 1.0

    def test_two_node_chain_correct_ordering(self):
        G = nx.DiGraph()
        G.add_node("W001", ref=None)
        G.add_node("W002", ref=None)
        G.add_edge("W001", "W002")
        report = InfluenceScorer.score(G)
        results = {r.paper_id: r for r in report.results}
        assert len(results) == 2
        # W002 is cited by W001 — cited paper accumulates PageRank
        assert results["W002"].rank == 1
        assert results["W001"].rank == 2

    def test_two_node_with_reverse_edge(self):
        G = nx.DiGraph()
        G.add_node("W001", ref=None)
        G.add_node("W002", ref=None)
        G.add_edge("W001", "W002")
        G.add_edge("W002", "W001")
        report = InfluenceScorer.score(G)
        assert len(report.results) == 2
        assert abs(report.results[0].score - report.results[1].score) < 0.01

    def test_star_graph_center_highest(self):
        G = nx.DiGraph()
        G.add_node("center")
        for i in range(5):
            leaf = f"leaf_{i}"
            G.add_node(leaf)
            G.add_edge(leaf, "center")
        report = InfluenceScorer.score(G)
        assert report.results[0].paper_id == "center"

    def test_linear_chain_three_nodes(self):
        G = nx.DiGraph()
        for i in range(3):
            G.add_node(f"W00{i}")
        G.add_edge("W000", "W001")
        G.add_edge("W001", "W002")
        report = InfluenceScorer.score(G)
        assert report.results[0].paper_id in ("W000", "W002")

    def test_scores_sum_to_one(self):
        G = nx.DiGraph()
        for i in range(5):
            G.add_node(f"W00{i}")
        for i in range(4):
            G.add_edge(f"W00{i}", f"W00{i+1}")
        report = InfluenceScorer.score(G)
        total = sum(r.score for r in report.results)
        assert abs(total - 1.0) < 0.01

    def test_ranks_are_contiguous(self):
        G = nx.DiGraph()
        for i in range(4):
            G.add_node(f"W00{i}")
        G.add_edge("W000", "W001")
        G.add_edge("W001", "W002")
        G.add_edge("W002", "W003")
        report = InfluenceScorer.score(G)
        ranks = [r.rank for r in report.results]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_custom_alpha(self):
        G = nx.DiGraph()
        G.add_node("W001", ref=None)
        G.add_node("W002", ref=None)
        G.add_edge("W001", "W002")
        report = InfluenceScorer.score(G, alpha=0.5)
        assert report.damping_factor == 0.5


class TestPageRankEgo:
    def test_ego_on_non_existent_node(self):
        G = nx.DiGraph()
        report = InfluenceScorer.score_ego(G, "missing")
        assert report.results == []

    def test_ego_depth_1_includes_neighbors(self):
        G = nx.DiGraph()
        G.add_node("center")
        for i in range(3):
            G.add_node(f"leaf_{i}")
            G.add_edge(f"leaf_{i}", "center")
        G.add_node("outsider")
        report = InfluenceScorer.score_ego(G, "center", depth=1)
        paper_ids = {r.paper_id for r in report.results}
        assert "center" in paper_ids
        assert "leaf_0" in paper_ids
        assert "leaf_1" in paper_ids
        assert "leaf_2" in paper_ids
        # "outsider" is not in the ego graph
        assert "outsider" not in paper_ids

    def test_ego_depth_0_returns_only_node(self):
        G = nx.DiGraph()
        G.add_node("center")
        G.add_edge("leaf_0", "center")
        report = InfluenceScorer.score_ego(G, "center", depth=0)
        assert len(report.results) == 1
        assert report.results[0].paper_id == "center"
