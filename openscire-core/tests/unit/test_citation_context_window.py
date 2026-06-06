"""Tests for CitationContextWindow."""

import math

import pytest
from openscire.references.chunking.models import ChunkMetadata, DocumentChunk
from openscire.references.citation.window import CitationContextWindow
from openscire.references.graph.builder import CitationGraphBuilder
from openscire.references.graph.influence import InfluenceScorer
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


def _make_ref(
    pid: str,
    title: str = "",
    year: int | None = None,
    citation_count: int = 0,
    doi: str = "",
    retraction_status: str = "",
    extra: dict | None = None,
    authors: list[ReferenceAuthor] | None = None,
) -> ReferenceItem:
    merged_extra = {**(extra or {}), "citation_count": citation_count}
    return ReferenceItem(
        id=pid,
        source=ReferenceSource.openalex,
        title=title,
        year=year,
        doi=doi,
        retraction_status=retraction_status,
        extra=merged_extra,
        authors=authors or [],
    )


def _make_chunk(
    chunk_id: str,
    text: str,
    citation_list: list[str] | None = None,
    section: str = "",
) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            document_id=chunk_id.split(":")[0] if ":" in chunk_id else chunk_id,
            section=section,
            citation_list=citation_list or [],
        ),
    )


class TestCitationExtraction:
    def test_extracts_citations_from_list(self) -> None:
        ref_a = _make_ref("W001", "Paper A", 2020)
        lookup = {"(Smith, 2020)": ref_a}
        window = CitationContextWindow(lookup)
        chunk = _make_chunk("doc:0", "Text (Smith, 2020) here", citation_list=["(Smith, 2020)"])
        report = window.build([chunk])
        assert len(report.citations) == 1
        assert report.citations[0].citation_text == "(Smith, 2020)"
        assert report.citations[0].reference_id == "W001"

    def test_unresolved_citation_included(self) -> None:
        lookup: dict = {}
        window = CitationContextWindow(lookup)
        chunk = _make_chunk("doc:0", "Text (Unknown, 2020) here", citation_list=["(Unknown, 2020)"])
        report = window.build([chunk])
        assert len(report.citations) == 1
        assert report.citations[0].reference_id == ""

    def test_extracts_sentence_context(self) -> None:
        ref_a = _make_ref("W001", "Paper A", 2020)
        lookup = {"[1]": ref_a}
        window = CitationContextWindow(lookup)
        text = (
            "Previous work showed this. Key finding from [1] supports our hypothesis. "
            "Another unrelated sentence."
        )
        chunk = _make_chunk("doc:0", text, citation_list=["[1]"])
        report = window.build([chunk])
        assert len(report.citations) == 1
        assert "Key finding from" in report.citations[0].sentence


class TestCitationResolution:
    def test_resolves_authors_into_string(self) -> None:
        authors = [ReferenceAuthor(first="John", last="Smith", full="John Smith")]
        ref_a = _make_ref("W001", "Paper A", 2020, authors=authors)
        lookup = {"(Smith, 2020)": ref_a}
        window = CitationContextWindow(lookup)
        chunk = _make_chunk("doc:0", "Text (Smith, 2020)", citation_list=["(Smith, 2020)"])
        report = window.build([chunk])
        assert report.citations[0].authors == "John Smith"

    def test_resolves_retraction_flag(self) -> None:
        ref_a = _make_ref("W001", "Retracted Paper", 2020, retraction_status="retracted")
        lookup = {"[1]": ref_a}
        window = CitationContextWindow(lookup)
        chunk = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        report = window.build([chunk])
        assert report.citations[0].is_retracted is True

    def test_non_retracted_not_flagged(self) -> None:
        ref_a = _make_ref("W001", "Clean Paper", 2020)
        lookup = {"[1]": ref_a}
        window = CitationContextWindow(lookup)
        chunk = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        report = window.build([chunk])
        assert report.citations[0].is_retracted is False


class TestNeighborhood:
    def test_outgoing_neighbors(self) -> None:
        ref_a = _make_ref(
            "W001",
            "Citing Paper",
            2020,
            extra={"referenced_works": ["https://api.openalex.org/W002"]},
        )
        ref_b = _make_ref("W002", "Cited Paper", 2019)
        lookup = {"[1]": ref_a, "[2]": ref_b}
        window = CitationContextWindow(
            lookup,
            graph_builder=CitationGraphBuilder(),
            influence_scorer=InfluenceScorer(),
        )
        chunk_a = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        chunk_b = _make_chunk("doc:1", "Text [2]", citation_list=["[2]"])
        report = window.build([chunk_a, chunk_b])
        neighbor_ids = {n.paper_id for n in report.neighborhood}
        assert "W002" in neighbor_ids

    def test_incoming_neighbors(self) -> None:
        ref_a = _make_ref("W001", "Citing Paper", 2020)
        ref_b = _make_ref(
            "W002",
            "Cited Paper",
            2019,
            extra={"referenced_works": ["https://api.openalex.org/W001"]},
        )
        lookup = {"[1]": ref_a, "[2]": ref_b}
        window = CitationContextWindow(
            lookup,
            graph_builder=CitationGraphBuilder(),
            influence_scorer=InfluenceScorer(),
        )
        chunk_a = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        chunk_b = _make_chunk("doc:1", "Text [2]", citation_list=["[2]"])
        report = window.build([chunk_a, chunk_b])
        neighbor_ids = {n.paper_id for n in report.neighborhood}
        assert "W001" in neighbor_ids

    def test_no_graph_builder_skips_neighborhood(self) -> None:
        ref_a = _make_ref("W001", "Paper A", 2020)
        lookup = {"[1]": ref_a}
        window = CitationContextWindow(lookup)
        chunk = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        report = window.build([chunk])
        assert len(report.neighborhood) == 0


class TestDensity:
    def test_density_includes_all_metrics(self) -> None:
        ref_a = _make_ref("W001", "Highly Cited", 2020, citation_count=50)
        ref_b = _make_ref("W002", "Moderately Cited", 2021, citation_count=20)
        lookup = {"[1]": ref_a, "[2]": ref_b}
        window = CitationContextWindow(
            lookup,
            graph_builder=CitationGraphBuilder(),
            influence_scorer=InfluenceScorer(),
        )
        chunk_a = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        chunk_b = _make_chunk("doc:1", "Text [2]", citation_list=["[2]"])
        report = window.build([chunk_a, chunk_b])
        assert len(report.density_scores) == 2
        for ds in report.density_scores:
            assert repr(ds.citation_count) != ""
            assert isinstance(ds.normalized_citation_count, float)
            assert isinstance(ds.pagerank_score, float)
            assert ds.density_label in ("high", "medium", "low")

    def test_density_thresholds(self) -> None:
        ref_high = _make_ref("W001", "Very Cited", 2020, citation_count=200)
        ref_mid = _make_ref("W002", "Mid Cited", 2020, citation_count=10)
        ref_low1 = _make_ref("W003", "Low Cited", 2020, citation_count=0)
        ref_low2 = _make_ref("W004", "Low Cited 2", 2020, citation_count=0)
        lookup = {"[1]": ref_high, "[2]": ref_mid, "[3]": ref_low1, "[4]": ref_low2}
        window = CitationContextWindow(lookup)
        chunks = [
            _make_chunk("doc:0", "Text [1]", citation_list=["[1]"]),
            _make_chunk("doc:1", "Text [2]", citation_list=["[2]"]),
            _make_chunk("doc:2", "Text [3]", citation_list=["[3]"]),
            _make_chunk("doc:3", "Text [4]", citation_list=["[4]"]),
        ]
        report = window.build(chunks)
        scores_by_id = {s.reference_id: s for s in report.density_scores}
        assert scores_by_id["W001"].density_label == "high"
        assert scores_by_id["W003"].density_label == "low"


class TestTemporalWeight:
    def test_exponential_decay(self) -> None:
        ref_recent = _make_ref("W001", "Recent", 2025)
        ref_old = _make_ref("W002", "Old", 2010)
        lookup = {"[1]": ref_recent, "[2]": ref_old}
        window = CitationContextWindow(lookup, current_year=2026, decay_rate=0.1)
        chunk_a = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        chunk_b = _make_chunk("doc:1", "Text [2]", citation_list=["[2]"])
        report = window.build([chunk_a, chunk_b])
        weights_by_id = {w.reference_id: w for w in report.temporal_weights}
        assert weights_by_id["W001"].weight > weights_by_id["W002"].weight

    def test_exact_weight_values(self) -> None:
        ref = _make_ref("W001", "Paper", 2020)
        lookup = {"[1]": ref}
        window = CitationContextWindow(lookup, current_year=2026, decay_rate=0.1)
        chunk = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        report = window.build([chunk])
        expected = math.exp(-0.1 * 6)
        assert report.temporal_weights[0].weight == pytest.approx(expected, rel=1e-4)

    def test_configurable_decay_rate(self) -> None:
        ref = _make_ref("W001", "Paper", 2020)
        lookup = {"[1]": ref}
        window = CitationContextWindow(lookup, current_year=2026, decay_rate=0.5)
        chunk = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        report = window.build([chunk])
        expected = math.exp(-0.5 * 6)
        assert report.temporal_weights[0].weight == pytest.approx(expected, rel=1e-4)

    def test_unknown_year_weight_zero(self) -> None:
        ref = _make_ref("W001", "No Year", year=None)
        lookup = {"[1]": ref}
        window = CitationContextWindow(lookup, current_year=2026)
        chunk = _make_chunk("doc:0", "Text [1]", citation_list=["[1]"])
        report = window.build([chunk])
        assert report.temporal_weights[0].weight == 0.0


class TestReportStructure:
    def test_full_report_has_all_sections(self) -> None:
        ref_a = _make_ref("W001", "Paper A", 2020, citation_count=10)
        ref_b = _make_ref("W002", "Paper B", 2021, citation_count=5)
        lookup = {"[1]": ref_a, "[2]": ref_b}
        window = CitationContextWindow(
            lookup,
            graph_builder=CitationGraphBuilder(),
            influence_scorer=InfluenceScorer(),
        )
        chunks = [
            _make_chunk("doc:0", "Text [1]", citation_list=["[1]"], section="Intro"),
            _make_chunk("doc:1", "Text [2]", citation_list=["[2]"], section="Methods"),
        ]
        report = window.build(chunks, query="test query")
        assert report.query == "test query"
        assert report.source_chunk_ids == ["doc:0", "doc:1"]
        assert len(report.citations) == 2
        assert isinstance(report.neighborhood, list)
        assert len(report.density_scores) == 2
        assert isinstance(report.contradictions, list)
        assert len(report.temporal_weights) == 2

    def test_empty_chunks(self) -> None:
        window = CitationContextWindow({})
        report = window.build([], query="empty")
        assert report.query == "empty"
        assert report.source_chunk_ids == []
        assert len(report.citations) == 0
        assert len(report.neighborhood) == 0
        assert len(report.density_scores) == 0
        assert len(report.contradictions) == 0
        assert len(report.temporal_weights) == 0

    def test_chunks_with_no_citations(self) -> None:
        window = CitationContextWindow({})
        chunk = _make_chunk("doc:0", "Plain text with no citations", citation_list=[])
        report = window.build([chunk])
        assert len(report.citations) == 0
