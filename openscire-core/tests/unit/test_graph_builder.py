# SPDX-License-Identifier: Apache-2.0

"""Tests for CitationGraphBuilder."""

from openscire.references.graph.builder import CitationGraphBuilder
from openscire.references.models import (
    CitationGraphEntry,
    ReferenceAuthor,
    ReferenceItem,
    ReferenceSource,
)


def _make_ref(pid: str, title: str = "", year: int | None = None, extra: dict | None = None) -> ReferenceItem:
    return ReferenceItem(
        id=pid,
        source=ReferenceSource.openalex,
        title=title,
        year=year,
        extra=extra or {},
    )


class TestBuild:
    def test_empty_list_returns_empty_graph(self):
        G = CitationGraphBuilder.build([])
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_single_node_no_edges(self):
        ref = _make_ref("W001", "Single Paper", 2020)
        G = CitationGraphBuilder.build([ref])
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0
        assert G.nodes["W001"]["ref"] is ref

    def test_two_unconnected_papers(self):
        r1 = _make_ref("W001", "Paper A", 2020)
        r2 = _make_ref("W002", "Paper B", 2021)
        G = CitationGraphBuilder.build([r1, r2])
        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 0

    def test_extracts_referenced_works_edges(self):
        r1 = _make_ref("W001", "Citing", 2020)
        r2 = _make_ref("W002", "Cited", 2019)
        r1.extra["referenced_works"] = ["https://api.openalex.org/W002"]
        G = CitationGraphBuilder.build([r1, r2])
        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 1
        assert G.has_edge("W001", "W002")

    def test_extracts_related_works_edges(self):
        r1 = _make_ref("W001", "Paper A", 2020)
        r2 = _make_ref("W002", "Paper B", 2021)
        r1.extra["related_works"] = ["https://api.openalex.org/W002"]
        G = CitationGraphBuilder.build([r1, r2])
        assert G.number_of_edges() == 1
        assert G.has_edge("W001", "W002")

    def test_skips_referenced_not_in_graph(self):
        r1 = _make_ref("W001", "Citing", 2020)
        r1.extra["referenced_works"] = ["https://api.openalex.org/W999"]
        G = CitationGraphBuilder.build([r1])
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0

    def test_handles_missing_extra(self):
        ref = _make_ref("W001", "No Extra")
        G = CitationGraphBuilder.build([ref])
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0


class TestBuildFromEntries:
    def test_single_citation_edge(self):
        citing = _make_ref("W001", "Citing", 2020)
        cited = _make_ref("W002", "Cited", 2019)
        entry = CitationGraphEntry(
            citing_paper=citing,
            cited_paper=cited,
            contexts=["As shown in [1]"],
            is_influential=True,
        )
        lookup = {"W001": citing, "W002": cited}
        G = CitationGraphBuilder.build_from_entries([entry], lookup)
        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 1
        assert G.has_edge("W001", "W002")
        assert G.edges["W001", "W002"]["is_influential"] is True

    def test_empty_entries(self):
        G = CitationGraphBuilder.build_from_entries([], {})
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_duplicate_nodes(self):
        ref = _make_ref("W001", "Duplicate")
        entry = CitationGraphEntry(citing_paper=ref, cited_paper=ref)
        G = CitationGraphBuilder.build_from_entries([entry, entry], {"W001": ref})
        assert G.number_of_nodes() == 1

    def test_handles_citing_only(self):
        citing = _make_ref("W001", "Citing Only", 2020)
        entry = CitationGraphEntry(citing_paper=citing, cited_paper=None)
        G = CitationGraphBuilder.build_from_entries([entry], {})
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0

    def test_handles_cited_only(self):
        cited = _make_ref("W002", "Cited Only", 2019)
        entry = CitationGraphEntry(citing_paper=None, cited_paper=cited)
        G = CitationGraphBuilder.build_from_entries([entry], {})
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0
