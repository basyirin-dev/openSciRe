from openscire.references.indexing.models import IndexedDocument, SearchResult
from openscire.references.indexing.reranker import CrossEncoderReranker


class TestCrossEncoderReranker:
    def test_unavailable_model(self):
        reranker = CrossEncoderReranker("nonexistent-model-xyz-123")
        doc1 = IndexedDocument(id="d1", text="Test document one")
        doc2 = IndexedDocument(id="d2", text="Test document two")
        results = [
            SearchResult(document=doc1, score=0.9, rank=1),
            SearchResult(document=doc2, score=0.8, rank=2),
        ]
        reranked = reranker.rerank("test query", results, top_k=2)
        assert len(reranked) == 2
        assert reranked[0].rank == 1

    def test_empty_results(self):
        reranker = CrossEncoderReranker()
        assert reranker.rerank("test query", []) == []

    def test_returns_original_on_failure(self, mocker):
        reranker = CrossEncoderReranker("test-model")
        mocker.patch.object(reranker, "_lazy_init", return_value=False)
        doc = IndexedDocument(id="d1", text="Test")
        results = [SearchResult(document=doc, score=0.9)]
        reranked = reranker.rerank("query", results, top_k=5)
        assert len(reranked) == 1
