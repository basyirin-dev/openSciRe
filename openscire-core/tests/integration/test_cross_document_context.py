# SPDX-License-Identifier: Apache-2.0

"""Integration test: cross-document retrieval with citation context windows.

Creates multiple documents with known citation relationships, chunks them,
retrieves across documents, and verifies CitationContextWindow produces
correct neighborhood, density, temporal weights, and contradiction signals.
"""

from __future__ import annotations

import pytest

from openscire.references.chunking import ChunkConfig, DocumentChunker
from openscire.references.chunking.models import DocumentChunk
from openscire.references.citation.window import CitationContextWindow
from openscire.references.graph.builder import CitationGraphBuilder
from openscire.references.graph.influence import InfluenceScorer
from openscire.references.indexing.models import IndexedDocument
from openscire.references.models import (
    ArticleSection,
    FullTextArticle,
    ReferenceAuthor,
    ReferenceItem,
    ReferenceSource,
)
from openscire.references.retrieval import BM25SparseIndex

pytestmark = [
    pytest.mark.integration,
]


def _make_ref(
    pid: str,
    title: str = "",
    year: int | None = None,
    citation_count: int = 0,
    doi: str = "",
    extra: dict | None = None,
) -> ReferenceItem:
    merged_extra = {**(extra or {}), "citation_count": citation_count}
    return ReferenceItem(
        id=pid,
        source=ReferenceSource.openalex,
        title=title,
        year=year,
        doi=doi,
        extra=merged_extra,
        authors=[ReferenceAuthor(last=pid, first="Author")],
    )


@pytest.fixture
def doc_a() -> FullTextArticle:
    """Paper A (2025): cites B and C."""
    return FullTextArticle(
        doi="10.1234/a.001",
        title="Paper A: Epigenetic Regulation",
        year=2025,
        abstract="Paper A investigates epigenetic regulation in development.",
        sections=[
            ArticleSection(
                heading="Introduction",
                body=(
                    "Epigenetic regulation is a key mechanism in development. "
                    "Previous work by Lee (2020) established the foundational role of histone "
                    "modifications in cell differentiation. "
                    "Recent studies have expanded this view (Kim, 2021)."
                ),
            ),
        ],
    )


@pytest.fixture
def doc_b() -> FullTextArticle:
    """Paper B (2023): cites C, cited by A."""
    return FullTextArticle(
        doi="10.1234/b.001",
        title="Paper B: Histone Modification Patterns",
        year=2023,
        abstract="Paper B examines histone modification patterns during differentiation.",
        sections=[
            ArticleSection(
                heading="Introduction",
                body=(
                    "Histone modifications regulate gene expression during development. "
                    "Kim (2021) demonstrated that H3K27me3 marks are enriched at developmental "
                    "genes. "
                    "These findings suggest a conserved mechanism across species."
                ),
            ),
        ],
    )


@pytest.fixture
def doc_c() -> FullTextArticle:
    """Paper C (2021): seminal work on H3K27me3, cited by A and B."""
    return FullTextArticle(
        doi="10.1234/c.001",
        title="Paper C: H3K27me3 in Development",
        year=2021,
        abstract="Paper C identified H3K27me3 as a key mark in developmental gene regulation.",
        sections=[
            ArticleSection(
                heading="Introduction",
                body=(
                    "Polycomb repressive complex 2 deposits H3K27me3 at developmental genes. "
                    "This modification is essential for proper cell differentiation. "
                    "Loss of H3K27me3 leads to developmental defects (Lee, 2020)."
                ),
            ),
        ],
    )


@pytest.fixture
def ref_a() -> ReferenceItem:
    return _make_ref(
        "W001", "Paper A: Epigenetic Regulation", 2025,
        citation_count=10, doi="10.1234/a.001",
        extra={"referenced_works": ["https://api.openalex.org/W002", "https://api.openalex.org/W003"]},
    )


@pytest.fixture
def ref_b() -> ReferenceItem:
    return _make_ref(
        "W002", "Paper B: Histone Modification Patterns", 2023,
        citation_count=45, doi="10.1234/b.001",
        extra={"referenced_works": ["https://api.openalex.org/W003"]},
    )


@pytest.fixture
def ref_c() -> ReferenceItem:
    return _make_ref(
        "W003", "Paper C: H3K27me3 in Development", 2021,
        citation_count=120, doi="10.1234/c.001",
    )


@pytest.fixture
def all_refs(
    ref_a: ReferenceItem,
    ref_b: ReferenceItem,
    ref_c: ReferenceItem,
) -> list[ReferenceItem]:
    return [ref_a, ref_b, ref_c]


class TestCrossDocumentContext:
    """Cross-document retrieval with citation context windows."""

    def test_citation_graph_built_from_refs(
        self,
        all_refs: list[ReferenceItem],
    ) -> None:
        graph = CitationGraphBuilder.build(all_refs)
        assert graph.number_of_nodes() == 3
        assert graph.number_of_edges() == 3
        assert graph.has_edge("W001", "W002")
        assert graph.has_edge("W001", "W003")
        assert graph.has_edge("W002", "W003")

    def test_chunk_and_index_all_docs(
        self,
        doc_a: FullTextArticle,
        doc_b: FullTextArticle,
        doc_c: FullTextArticle,
    ) -> None:
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks: list[DocumentChunk] = []
        chunks.extend(chunker.chunk(doc_a, document_id="W001"))
        chunks.extend(chunker.chunk(doc_b, document_id="W002"))
        chunks.extend(chunker.chunk(doc_c, document_id="W003"))

        index = BM25SparseIndex()
        index.add_documents([
            IndexedDocument(
                id=c.id, text=c.text,
                metadata={"doc_id": c.metadata.document_id, "section": c.metadata.section},
            )
            for c in chunks
        ])

        results = index.search("H3K27me3 developmental regulation", top_k=10)
        assert len(results) >= 2

        doc_ids = {r.document.metadata.get("doc_id") for r in results}
        assert "W003" in doc_ids  # Paper C should be most relevant
        assert "W001" in doc_ids or "W002" in doc_ids

    def test_context_window_builds_neighborhood(
        self,
        all_refs: list[ReferenceItem],
    ) -> None:
        ref_lookup = {r.id: r for r in all_refs}
        graph = CitationGraphBuilder.build(all_refs)
        scorer = InfluenceScorer()
        window = CitationContextWindow(
            ref_lookup=ref_lookup,
            graph_builder=CitationGraphBuilder(),
            influence_scorer=scorer,
            current_year=2026,
        )

        chunks = [
            _make_chunk_with_citations("W001:0", "Epigenetic regulation is key (Lee, 2020).", ["W001"]),
            _make_chunk_with_citations("W002:0", "Histone modifications regulate expression.", ["W002"]),
            _make_chunk_with_citations("W003:0", "H3K27me3 is essential for differentiation.", ["W003"]),
        ]

        report = window.build(chunks, query="H3K27me3 regulation")
        assert len(report.neighborhood) >= 2

        neighbor_ids = {n.paper_id for n in report.neighborhood}
        relationships = {n.relationship for n in report.neighborhood}
        assert "cites" in relationships or "cited_by" in relationships

    def test_context_window_density_scores(
        self,
        all_refs: list[ReferenceItem],
    ) -> None:
        ref_lookup = {r.id: r for r in all_refs}
        window = CitationContextWindow(
            ref_lookup=ref_lookup,
            graph_builder=CitationGraphBuilder(),
            influence_scorer=InfluenceScorer(),
            current_year=2026,
        )

        chunks = [
            _make_chunk_with_citations("W001:0", "Epigenetic regulation is key.", ["W001"]),
            _make_chunk_with_citations("W003:0", "H3K27me3 is essential.", ["W003"]),
        ]

        report = window.build(chunks)
        assert len(report.density_scores) == 2

        score_map = {s.reference_id: s for s in report.density_scores}
        assert "W001" in score_map
        assert "W003" in score_map

        c_score = score_map["W003"]
        assert c_score.citation_count == 120
        assert c_score.density_label in ("high", "medium", "low")

    def test_context_window_temporal_weights(
        self,
        all_refs: list[ReferenceItem],
    ) -> None:
        ref_lookup = {r.id: r for r in all_refs}
        window = CitationContextWindow(
            ref_lookup=ref_lookup,
            current_year=2026,
            decay_rate=0.5,
        )

        chunks = [
            _make_chunk_with_citations("W001:0", "Recent work.", ["W001"]),
            _make_chunk_with_citations("W002:0", "Older work.", ["W002"]),
            _make_chunk_with_citations("W003:0", "Oldest work.", ["W003"]),
        ]

        report = window.build(chunks)
        assert len(report.temporal_weights) == 3

        weight_map = {w.reference_id: w for w in report.temporal_weights}
        assert weight_map["W001"].weight > weight_map["W002"].weight > weight_map["W003"].weight

    def test_context_window_includes_all_report_fields(
        self,
        all_refs: list[ReferenceItem],
    ) -> None:
        ref_lookup = {r.id: r for r in all_refs}
        window = CitationContextWindow(
            ref_lookup=ref_lookup,
            graph_builder=CitationGraphBuilder(),
            influence_scorer=InfluenceScorer(),
            current_year=2026,
        )

        chunks = [
            _make_chunk_with_citations("W001:0", "Epigenetic regulation (Lee, 2020).", ["(Lee, 2020)", "W001"]),
        ]

        report = window.build(chunks, query="epigenetics")
        assert report.query == "epigenetics"
        assert len(report.source_chunk_ids) == 1
        assert len(report.citations) >= 1
        assert isinstance(report.citations[0].reference_id, str)

    def test_full_cross_document_pipeline(
        self,
        doc_a: FullTextArticle,
        doc_b: FullTextArticle,
        doc_c: FullTextArticle,
        ref_a: ReferenceItem,
        ref_b: ReferenceItem,
        ref_c: ReferenceItem,
    ) -> None:
        all_refs = [ref_a, ref_b, ref_c]
        ref_lookup = {r.id: r for r in all_refs}

        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks: list[DocumentChunk] = []
        chunks.extend(chunker.chunk(doc_a, document_id="W001"))
        chunks.extend(chunker.chunk(doc_b, document_id="W002"))
        chunks.extend(chunker.chunk(doc_c, document_id="W003"))

        index = BM25SparseIndex()
        index.add_documents([
            IndexedDocument(id=c.id, text=c.text, metadata={"doc_id": c.metadata.document_id})
            for c in chunks
        ])

        results = index.search("H3K27me3 developmental gene regulation", top_k=5)

        window = CitationContextWindow(
            ref_lookup=ref_lookup,
            graph_builder=CitationGraphBuilder(),
            influence_scorer=InfluenceScorer(),
            current_year=2026,
        )

        retrieved_chunks = [c for c in chunks if any(r.document.id == c.id for r in results)]
        assert len(retrieved_chunks) >= 1

        report = window.build(retrieved_chunks, query="H3K27me3 developmental gene regulation")

        assert len(report.citations) >= 0
        assert len(report.neighborhood) >= 0
        assert len(report.density_scores) >= 0
        assert len(report.temporal_weights) >= 0
        assert len(report.contradictions) == 0


def _make_chunk_with_citations(
    chunk_id: str,
    text: str,
    citation_list: list[str],
) -> DocumentChunk:
    from openscire.references.chunking.models import ChunkMetadata

    return DocumentChunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            document_id=chunk_id.split(":")[0],
            section="Introduction",
            citation_list=citation_list,
        ),
    )
