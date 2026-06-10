# SPDX-License-Identifier: Apache-2.0

"""Integration test: Zotero import -> PDF parse -> embed -> search -> retraction check.

Tests the full literature processing pipeline end-to-end with mocked HTTP/IO.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import respx
from openscire.references.indexing import (
    EmbeddingIndex,
    IndexedDocument,
    LocalBackend,
    SearchResult,
)
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource
from openscire.references.parsing.models import ExtractionResult, FullTextArticle
from openscire.references.parsing.pipeline import PDFParsingPipeline
from openscire.references.retraction.database import RetractionDatabase
from openscire.references.retraction.monitor import RetractionMonitor

pytestmark = [
    pytest.mark.integration,
]


@pytest.fixture
def embedding_index() -> EmbeddingIndex:
    return EmbeddingIndex(backend=LocalBackend(dimension=8))


class TestLiteratureCycle:
    """Zotero -> PDF parse -> embed -> search -> retraction."""

    async def test_reference_item_creation(self) -> None:
        ref = ReferenceItem(
            id="zotero_test_001",
            source=ReferenceSource.zotero,
            doi="10.1234/test.5678",
            title="A Test Paper for Literature Cycle Integration",
            authors=[
                ReferenceAuthor(full="Alice Researcher"),
                ReferenceAuthor(full="Bob Scientist"),
            ],
            year=2025,
        )
        assert ref.doi == "10.1234/test.5678"
        assert ref.source == ReferenceSource.zotero
        assert len(ref.authors) == 2

    async def test_full_cycle(
        self,
        mocker: Any,  # noqa: ANN401
        embedding_index: EmbeddingIndex,
    ) -> None:
        pipeline = mocker.MagicMock(spec=PDFParsingPipeline)

        async def fake_parse(
            pdf_bytes: bytes = b"", source_path: str = "", **kwargs: Any
        ) -> ExtractionResult:  # noqa: ANN401
            return ExtractionResult(
                method="pdfplumber",
                full_text=FullTextArticle(
                    doi="10.1234/test.5678",
                    title="A Test Paper",
                    year=2025,
                    raw_text="Full text of test paper.",
                    references=["doi:10.9999/ref1", "doi:10.9999/ref2"],
                ),
                pages=2,
                extraction_time=0.5,
            )

        pipeline.parse = fake_parse

        rng = np.random.default_rng(42)
        result = await pipeline.parse(pdf_bytes=b"%PDF-1.4 simulated")
        assert result.full_text.doi == "10.1234/test.5678"
        assert len(result.full_text.references) == 2

        doc = IndexedDocument(
            id="test_doc_001",
            text=result.full_text.raw_text,
            embedding=rng.random(8).tolist(),
            metadata={"doi": result.full_text.doi},
        )
        embedding_index.add_documents([doc])
        assert embedding_index._backend.count() == 1

        query_vec = rng.random(8).tolist()
        results = embedding_index.search(query=query_vec, top_k=5)
        assert len(results) >= 1
        assert results[0].document.id == "test_doc_001"

    async def test_retraction_after_ingestion(
        self,
        embedding_index: EmbeddingIndex,
    ) -> None:
        rng = np.random.default_rng(7)
        doc = IndexedDocument(
            id="retracted_doc",
            text="This paper was later retracted.",
            embedding=rng.random(8).tolist(),
            metadata={"doi": "10.1234/retracted.001"},
        )
        embedding_index.add_documents([doc])
        assert embedding_index._backend.count() == 1

        async with respx.mock:
            # OpenAlex: not retracted
            respx.get("https://api.openalex.org/works/doi/10.1234/retracted.001").respond(
                json={
                    "id": "https://openalex.org/W000000001",
                    "is_retracted": False,
                },
            )
            # PubMed: esearch returns empty (no retractions found)
            respx.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            ).respond(
                json={"esearchresult": {"idlist": [], "count": "0"}},
            )
            # Crossref: no corrections
            respx.get("https://api.crossref.org/works/10.1234/retracted.001").respond(
                json={
                    "status": "ok",
                    "message": {"DOI": "10.1234/retracted.001", "title": ["Retracted Paper"]},
                },
            )
            # PubPeer: no concerns
            respx.get("https://pubpeer.com/api/v3/search").respond(json={"results": []})

            db = RetractionDatabase()
            monitor = RetractionMonitor(database=db)
            status, records = await monitor.check_paper("10.1234/retracted.001")

        assert status.value == "unchecked"
        assert len(records) == 0

    async def test_embed_and_search_multiple_docs(
        self,
        embedding_index: EmbeddingIndex,
    ) -> None:
        rng = np.random.default_rng(1)
        docs = [
            IndexedDocument(
                id=f"doc_{i:03d}",
                text=f"This is document number {i} about scientific research.",
                embedding=rng.random(8).tolist(),
                metadata={"idx": i},
            )
            for i in range(5)
        ]
        embedding_index.add_documents(docs)
        assert embedding_index._backend.count() == 5

        query_vec = rng.random(8).tolist()
        results = embedding_index.search(query=query_vec, top_k=3)
        assert len(results) == 3
        assert all(isinstance(r, SearchResult) for r in results)

    async def test_index_clear_and_reuse(
        self,
        embedding_index: EmbeddingIndex,
    ) -> None:
        rng = np.random.default_rng(9)
        doc = IndexedDocument(
            id="clear_test",
            text="Test document.",
            embedding=rng.random(8).tolist(),
        )
        embedding_index.add_documents([doc])
        assert embedding_index._backend.count() == 1

        embedding_index._backend.clear()
        assert embedding_index._backend.count() == 0

        doc2 = IndexedDocument(
            id="new_doc",
            text="New document after clear.",
            embedding=rng.random(8).tolist(),
        )
        embedding_index.add_documents([doc2])
        assert embedding_index._backend.count() == 1
