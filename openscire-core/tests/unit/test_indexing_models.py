from openscire.references.indexing.models import IndexedDocument, SearchResult


class TestIndexedDocument:
    def test_default_fields(self):
        doc = IndexedDocument(id="test-1")
        assert doc.id == "test-1"
        assert doc.text == ""
        assert doc.metadata == {}
        assert doc.embedding is None

    def test_with_all_fields(self):
        doc = IndexedDocument(
            id="test-2",
            text="Some paper text",
            metadata={"year": 2024, "author": "Smith"},
            embedding=[0.1, 0.2, 0.3],
        )
        assert doc.embedding == [0.1, 0.2, 0.3]
        assert doc.metadata["year"] == 2024


class TestSearchResult:
    def test_default_fields(self):
        doc = IndexedDocument(id="test-1")
        result = SearchResult(document=doc, score=0.95)
        assert result.score == 0.95
        assert result.rank == 0
        assert result.rerank_score is None

    def test_with_rerank(self):
        doc = IndexedDocument(id="test-1")
        result = SearchResult(document=doc, score=0.9, rank=1, rerank_score=0.95)
        assert result.rank == 1
        assert result.rerank_score == 0.95
