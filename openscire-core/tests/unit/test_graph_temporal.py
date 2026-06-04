# SPDX-License-Identifier: Apache-2.0

"""Tests for TemporalAnalyzer."""

import networkx as nx

from openscire.references.graph.models import YearCount
from openscire.references.graph.temporal import TemporalAnalyzer
from openscire.references.models import ReferenceItem, ReferenceSource


def _make_ref(pid: str, title: str = "", year: int | None = None, counts: list | None = None) -> ReferenceItem:
    extra = {}
    if counts is not None:
        extra["counts_by_year"] = counts
    return ReferenceItem(id=pid, source=ReferenceSource.openalex, title=title, year=year, extra=extra)


class TestTimeline:
    def setup_method(self):
        self.ta = TemporalAnalyzer()

    def test_empty_graph_returns_empty_list(self):
        assert self.ta.timeline(nx.DiGraph()) == []

    def test_node_without_counts(self):
        G = nx.DiGraph()
        ref = _make_ref("W001", "No Data", 2020)
        G.add_node("W001", ref=ref)
        tl = self.ta.timeline(G)
        assert len(tl) == 1
        assert tl[0].paper_id == "W001"
        assert tl[0].yearly_counts == []

    def test_node_with_counts(self):
        G = nx.DiGraph()
        counts = [
            {"year": 2020, "cited_by_count": 5},
            {"year": 2021, "cited_by_count": 10},
            {"year": 2022, "cited_by_count": 15},
        ]
        ref = _make_ref("W001", "Popular", 2020, counts)
        G.add_node("W001", ref=ref)
        tl = self.ta.timeline(G)
        assert len(tl) == 1
        assert len(tl[0].yearly_counts) == 3
        assert tl[0].yearly_counts[1] == YearCount(year=2021, count=10)
        assert tl[0].total_citations == 30

    def test_multiple_nodes(self):
        G = nx.DiGraph()
        r1 = _make_ref("W001", "A", 2020, [{"year": 2020, "cited_by_count": 1}])
        r2 = _make_ref("W002", "B", 2021, [{"year": 2021, "cited_by_count": 2}])
        G.add_node("W001", ref=r1)
        G.add_node("W002", ref=r2)
        tl = self.ta.timeline(G)
        assert len(tl) == 2

    def test_handle_invalid_counts_data(self):
        G = nx.DiGraph()
        ref = _make_ref("W001", "Bad", 2020, "not_a_list")
        G.add_node("W001", ref=ref)
        tl = self.ta.timeline(G)
        assert len(tl) == 1
        assert tl[0].yearly_counts == []

    def test_node_without_ref_attribute(self):
        G = nx.DiGraph()
        G.add_node("W001")
        tl = self.ta.timeline(G)
        assert len(tl) == 1
        assert tl[0].paper_id == "W001"
        assert tl[0].yearly_counts == []


class TestDecay:
    def setup_method(self):
        self.ta = TemporalAnalyzer()

    def test_empty_graph(self):
        report = self.ta.detect_decay(nx.DiGraph())
        assert report.results == []
        assert report.decayed_papers == []

    def test_insufficient_data_excluded(self):
        G = nx.DiGraph()
        ref = _make_ref("W001", "New Paper", 2025, [{"year": 2025, "cited_by_count": 1}])
        G.add_node("W001", ref=ref)
        report = self.ta.detect_decay(G)
        assert len(report.results) == 1
        assert not report.results[0].is_decayed
        assert "insufficient" in report.results[0].reason

    def test_actively_cited_not_decayed(self):
        G = nx.DiGraph()
        counts = [
            {"year": y, "cited_by_count": c}
            for y, c in [(2020, 10), (2021, 15), (2022, 20), (2023, 18), (2024, 22), (2025, 25)]
        ]
        ref = _make_ref("W001", "Active", 2020, counts)
        G.add_node("W001", ref=ref)
        report = self.ta.detect_decay(G, current_year=2026)
        assert not report.results[0].is_decayed
        assert report.healthy_papers == ["W001"]

    def test_decayed_paper_detected(self):
        G = nx.DiGraph()
        counts = [
            {"year": y, "cited_by_count": c}
            for y, c in [(2010, 50), (2011, 100), (2012, 80), (2013, 5), (2014, 2), (2015, 1)]
        ]
        ref = _make_ref("W001", "Old Classic", 2010, counts)
        G.add_node("W001", ref=ref)
        report = self.ta.detect_decay(G, current_year=2026)
        assert report.results[0].is_decayed
        assert report.decayed_papers == ["W001"]
        assert report.results[0].peak_year == 2011
        assert report.results[0].peak_velocity == 100

    def test_below_min_peak_excluded(self):
        ta = TemporalAnalyzer({"min_peak_citations": 50})
        G = nx.DiGraph()
        counts = [
            {"year": y, "cited_by_count": c}
            for y, c in [(2020, 5), (2021, 10), (2022, 8)]
        ]
        ref = _make_ref("W001", "Low Citations", 2020, counts)
        G.add_node("W001", ref=ref)
        report = ta.detect_decay(G)
        assert not report.results[0].is_decayed
        assert "below minimum" in report.results[0].reason

    def test_custom_threshold(self):
        ta = TemporalAnalyzer({"decay_threshold": 0.3})
        G = nx.DiGraph()
        counts = [
            {"year": y, "cited_by_count": c}
            for y, c in [(2015, 100), (2023, 40), (2024, 35), (2025, 30)]
        ]
        ref = _make_ref("W001", "Moderate Decline", 2015, counts)
        G.add_node("W001", ref=ref)
        report = ta.detect_decay(G, current_year=2026)
        assert report.threshold == 0.3

    def test_node_has_no_ref_attr(self):
        G = nx.DiGraph()
        G.add_node("W001")
        report = self.ta.detect_decay(G)
        assert len(report.results) == 1
        assert "no reference data" in report.results[0].reason

    def test_decay_score_formula(self):
        G = nx.DiGraph()
        counts = [
            {"year": y, "cited_by_count": c}
            for y, c in [(2010, 100), (2020, 100), (2021, 5), (2022, 5)]
        ]
        ref = _make_ref("W001", "Test", 2010, counts)
        G.add_node("W001", ref=ref)
        ta = TemporalAnalyzer({"decay_window": 3})
        report = ta.detect_decay(G, current_year=2023)
        r = report.results[0]
        assert abs(r.recent_velocity - 36.6667) < 0.1
        assert abs(r.decay_score - 0.6333) < 0.01
        assert r.peak_velocity == 100
        assert r.peak_year == 2010
