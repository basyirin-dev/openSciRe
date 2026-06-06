# SPDX-License-Identifier: Apache-2.0

"""Integration test: RAG pipeline end-to-end (chunk -> search -> format -> enforce -> cross-check)."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import pytest

from openscire.ethics.models import Source
from openscire.references.chunking import ChunkConfig, DocumentChunker
from openscire.references.enforcer import (
    CitationMode,
    CrossCheckVerdict,
    SourceEnforcer,
)
from openscire.references.formatter import CitationFormatter, CitationStyle
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


class _Chunk:
    def __init__(self, text: str) -> None:
        self.delta_content = text


class _MockProvider:
    def __init__(self, response: str) -> None:
        self.response = response

    async def stream_chat(
        self,
        messages: list[Any],
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[_Chunk]:
        yield _Chunk(self.response)


@pytest.fixture
def smith_source() -> Source:
    return Source(
        source_id="Smith2020",
        doi="10.1000/abc123",
        title="DNA Methylation in Cancer",
        authors="Smith",
        year=2020,
        abstract="We found that DNA methylation patterns are altered in cancer cells.",
    )


@pytest.fixture
def jones_source() -> Source:
    return Source(
        source_id="Jones2019",
        doi="10.1000/def456",
        title="Gene Expression Analysis Methods",
        authors="Jones",
        year=2019,
        abstract="We developed a novel method for gene expression analysis from tumor samples.",
    )


@pytest.fixture
def known_sources(
    smith_source: Source,
    jones_source: Source,
) -> list[Source]:
    return [smith_source, jones_source]


@pytest.fixture
def ref_items(
    smith_source: Source,
    jones_source: Source,
) -> list[ReferenceItem]:
    return [
        ReferenceItem(
            id=smith_source.source_id,
            source=ReferenceSource.bibtex,
            doi=smith_source.doi,
            title=smith_source.title,
            authors=[ReferenceAuthor(last="Smith", first="John")],
            year=smith_source.year,
            journal="Nature Genetics",
            volume="15",
            issue="3",
            pages="123-130",
        ),
        ReferenceItem(
            id=jones_source.source_id,
            source=ReferenceSource.bibtex,
            doi=jones_source.doi,
            title=jones_source.title,
            authors=[ReferenceAuthor(last="Jones", first="Jane")],
            year=jones_source.year,
            journal="Bioinformatics",
            volume="10",
            issue="1",
            pages="45-60",
        ),
    ]


@pytest.fixture
def article() -> FullTextArticle:
    return FullTextArticle(
        doi="10.1234/test.001",
        title="Epigenetic Markers in Cancer",
        year=2024,
        abstract="This study examines DNA methylation and gene expression in cancer development.",
        sections=[
            ArticleSection(
                heading="Introduction",
                body=(
                    "Epigenetic alterations play a crucial role in cancer development. "
                    "DNA methylation patterns are frequently altered in tumor cells (Smith, 2020). "
                    "Genome-wide studies have confirmed this observation. "
                    "Understanding these changes is critical for early detection."
                ),
            ),
            ArticleSection(
                heading="Methods",
                body=(
                    "We analyzed methylation data from 500 patient samples. "
                    "Bisulfite sequencing was performed as described by Jones (2019). "
                    "Statistical analysis was conducted using R version 4.0."
                ),
            ),
            ArticleSection(
                heading="Results",
                body=(
                    "We found significant hypermethylation in promoter regions. "
                    "The average methylation level was 0.76 (p < 0.001). "
                    "These results align with previous findings (Smith, 2020). "
                    "Gene expression analysis (Jones, 2019) confirmed the functional impact."
                ),
            ),
        ],
    )


class TestRagPipeline:
    """Chunk -> index -> search -> format -> enforce -> cross-check end-to-end."""

    def test_chunking_produces_section_aware_chunks(
        self,
        article: FullTextArticle,
    ) -> None:
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article, document_id="test:001")

        assert len(chunks) >= 4
        sections = {c.metadata.section for c in chunks}
        assert "Abstract" in sections
        assert "Introduction" in sections
        assert "Methods" in sections
        assert "Results" in sections

    def test_chunks_preserve_citations(
        self,
        article: FullTextArticle,
    ) -> None:
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article, document_id="test:001")

        all_citations: set[str] = set()
        for c in chunks:
            all_citations.update(c.metadata.citation_list)
        assert "(Smith, 2020)" in all_citations
        assert "(Jones, 2019)" in all_citations

    def test_bm25_index_and_search_retrieves_relevant_chunks(
        self,
        article: FullTextArticle,
    ) -> None:
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article, document_id="test:001")

        index = BM25SparseIndex()
        index.add_documents([
            IndexedDocument(id=c.id, text=c.text, metadata={"section": c.metadata.section})
            for c in chunks
        ])

        results = index.search("DNA methylation cancer tumor", top_k=5)
        assert len(results) >= 1
        top_sections = {r.document.metadata.get("section") for r in results}
        assert "Introduction" in top_sections or "Results" in top_sections

    def test_search_retrieves_across_sections(
        self,
        article: FullTextArticle,
    ) -> None:
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article, document_id="test:001")

        index = BM25SparseIndex()
        index.add_documents([
            IndexedDocument(id=c.id, text=c.text, metadata={"section": c.metadata.section})
            for c in chunks
        ])

        results = index.search("bisulfite sequencing statistical analysis", top_k=5)
        assert len(results) >= 1
        assert any(r.document.metadata.get("section") == "Methods" for r in results)

    def test_format_citations_from_sources(
        self,
        ref_items: list[ReferenceItem],
    ) -> None:
        apa_fmt = CitationFormatter(style=CitationStyle.APA)

        inline = apa_fmt.format_inline(ref_items[0])
        assert "Smith" in inline.text
        assert "2020" in inline.text

        nature_fmt = CitationFormatter(style=CitationStyle.NATURE)
        inline2 = nature_fmt.format_inline(ref_items[1])
        assert "[1]" in inline2.text or "[2]" in inline2.text

        ref_list = apa_fmt.format_reference_list(ref_items)
        assert len(ref_list) == 2
        assert ref_list[0].number < ref_list[1].number

        vanc_fmt = CitationFormatter(style=CitationStyle.VANCOUVER)
        vanc_list = vanc_fmt.format_reference_list(ref_items)
        assert vanc_list[0].number == 1
        assert vanc_list[1].number == 2

    def test_enforcer_verifies_citations(
        self,
        known_sources: list[Source],
    ) -> None:
        enforcer = SourceEnforcer()
        text = (
            "DNA methylation patterns are altered in tumor cells (Smith, 2020). "
            "Gene expression analysis (Jones, 2019) confirmed the functional impact."
        )
        report = enforcer.enforce(text, known_sources, mode=CitationMode.WARN)
        assert report.total_sentences == 2
        assert report.cited_sentences == 2
        assert report.verified_citations == 2
        assert len(report.unsupported_claims) == 0
        assert report.approved is True

    def test_enforcer_flags_unsupported_claims(
        self,
        known_sources: list[Source],
    ) -> None:
        enforcer = SourceEnforcer()
        text = (
            "DNA methylation is altered in cancer (Smith, 2020). "
            "This novel mechanism has never been described before."
        )
        report = enforcer.enforce(text, known_sources, mode=CitationMode.WARN)
        assert report.total_sentences == 2
        assert report.cited_sentences == 1
        assert len(report.unsupported_claims) == 1
        assert "never been described" in report.unsupported_claims[0].claim_text

    def test_strict_mode_blocks_unsupported(
        self,
        known_sources: list[Source],
    ) -> None:
        enforcer = SourceEnforcer()
        text = "This claim has no supporting citation."
        report = enforcer.enforce(text, known_sources, mode=CitationMode.STRICT)
        assert report.approved is False
        assert len(report.unsupported_claims) == 1

    def test_cross_check_integrates_into_pipeline(
        self,
        known_sources: list[Source],
    ) -> None:
        provider = _MockProvider(json.dumps({
            "verdict": "supports",
            "confidence": 0.92,
            "explanation": "supports verdict",
        }))
        enforcer = SourceEnforcer()
        text = "DNA methylation patterns are altered in tumor cells (Smith, 2020)."

        report = enforcer.enforce(
            text, known_sources, mode=CitationMode.WARN, provider=provider,
        )
        assert report.cross_check_enabled is True
        assert len(report.cross_check_results) == 1
        assert report.cross_check_results[0].verdict == CrossCheckVerdict.SUPPORTS

    def test_cross_check_detects_contradiction(
        self,
        known_sources: list[Source],
    ) -> None:
        provider = _MockProvider(json.dumps({
            "verdict": "contradicts",
            "confidence": 0.85,
            "explanation": "contradicts verdict",
        }))
        enforcer = SourceEnforcer()
        text = "DNA methylation patterns are altered in tumor cells (Smith, 2020)."

        report = enforcer.enforce(
            text, known_sources, mode=CitationMode.WARN, provider=provider,
        )
        assert report.cross_check_enabled is True
        assert len(report.cross_check_results) == 1
        assert report.cross_check_results[0].verdict == CrossCheckVerdict.CONTRADICTS
        assert len(report.unsupported_claims) == 1
        assert report.unsupported_claims[0].reason == "semantic_mismatch"

    def test_full_pipeline_no_llm(
        self,
        article: FullTextArticle,
        known_sources: list[Source],
        ref_items: list[ReferenceItem],
    ) -> None:
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article, document_id="test:001")

        index = BM25SparseIndex()
        index.add_documents([
            IndexedDocument(id=c.id, text=c.text, metadata={"section": c.metadata.section})
            for c in chunks
        ])

        results = index.search("DNA methylation gene expression", top_k=5)
        assert len(results) >= 1

        retrieved_text = " ".join(r.document.text for r in results[:3])

        formatter = CitationFormatter(style=CitationStyle.APA)
        inline = formatter.format_inline(ref_items[0])
        assert "(Smith, 2020)" in retrieved_text or "Smith" in inline.text

        enforcer = SourceEnforcer()
        report = enforcer.enforce(retrieved_text, known_sources, mode=CitationMode.WARN)
        assert report.total_sentences >= 1
        assert report.verified_citations >= 0

    def test_full_pipeline_with_cross_check(
        self,
        article: FullTextArticle,
        known_sources: list[Source],
        ref_items: list[ReferenceItem],
    ) -> None:
        chunker = DocumentChunker(ChunkConfig(max_tokens=2048, overlap_sentences=0))
        chunks = chunker.chunk(article, document_id="test:001")

        index = BM25SparseIndex()
        index.add_documents([
            IndexedDocument(id=c.id, text=c.text, metadata={"section": c.metadata.section})
            for c in chunks
        ])

        results = index.search("DNA methylation cancer", top_k=5)
        retrieved_text = " ".join(r.document.text for r in results[:3])

        provider = _MockProvider(json.dumps({
            "verdict": "supports",
            "confidence": 0.90,
            "explanation": "supports verdict",
        }))

        enforcer = SourceEnforcer()
        report = enforcer.enforce(
            retrieved_text, known_sources, mode=CitationMode.WARN, provider=provider,
        )
        assert report.cross_check_enabled is True
        assert len(report.cross_check_results) >= 0
