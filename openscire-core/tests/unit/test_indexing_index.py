import pytest
from openscire.references.indexing.filters import field
from openscire.references.indexing.index import EmbeddingIndex
from openscire.references.indexing.models import IndexedDocument


class MockBackend:
    def __init__(self):
        self._data: dict[str, tuple[list[float], dict]] = {}

    def add(self, ids, vectors, metadatas=None):
        for i, doc_id in enumerate(ids):
            self._data[doc_id] = (vectors[i], metadatas[i] if metadatas else {})

    def search(self, query_vector, top_k=10):
        import numpy as np

        query = np.array(query_vector)
        query = query / (np.linalg.norm(query) + 1e-10)
        scored = []
        for doc_id, (vec, meta) in self._data.items():
            v = np.array(vec)
            v = v / (np.linalg.norm(v) + 1e-10)
            score = float(np.dot(query, v))
            scored.append((doc_id, score, meta))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def delete(self, ids):
        for doc_id in ids:
            self._data.pop(doc_id, None)

    def count(self):
        return len(self._data)

    def save(self, path):
        pass

    def load(self, path):
        pass

    def clear(self):
        self._data.clear()


class MockEmbedder:
    def encode(self, texts):
        import hashlib

        result = []
        for t in texts:
            h = hashlib.md5(t.encode()).digest()
            vec = [b / 255.0 for b in h[:4]]
            result.append(vec)
        return result

    def encode_query(self, query):
        return self.encode([query])[0]


class TestEmbeddingIndex:
    def test_add_and_search(self):
        backend = MockBackend()
        index = EmbeddingIndex(backend=backend, embedder=MockEmbedder())
        docs = [
            IndexedDocument(id="doc1", text="Machine learning paper"),
            IndexedDocument(id="doc2", text="Biology research paper"),
            IndexedDocument(id="doc3", text="Physics theory paper"),
        ]
        index.add_documents(docs)
        assert index.count() == 3

    def test_search_with_precomputed_embeddings(self):
        backend = MockBackend()
        index = EmbeddingIndex(backend=backend)
        docs = [
            IndexedDocument(
                id="doc1",
                text="Paper",
                embedding=[1.0, 0.0, 0.0, 0.0],
                metadata={"title": "Paper 1"},
            ),
        ]
        index.add_documents(docs)
        results = index.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert len(results) == 1
        assert results[0].document.id == "doc1"
        assert results[0].score > 0.99

    def test_metadata_filter(self):
        backend = MockBackend()
        index = EmbeddingIndex(backend=backend, embedder=MockEmbedder())
        docs = [
            IndexedDocument(id="d1", text="ML paper", metadata={"year": 2024, "topic": "ai"}),
            IndexedDocument(id="d2", text="Bio paper", metadata={"year": 2023, "topic": "bio"}),
            IndexedDocument(id="d3", text="AI paper", metadata={"year": 2024, "topic": "ai"}),
        ]
        index.add_documents(docs)
        results = index.search(
            [1.0, 0.0, 0.0, 0.0],
            top_k=10,
            filters=field("year", "eq", 2024),
        )
        assert len(results) == 2
        assert all(r.document.metadata["year"] == 2024 for r in results)

    def test_delete(self):
        backend = MockBackend()
        index = EmbeddingIndex(backend=backend, embedder=MockEmbedder())
        docs = [
            IndexedDocument(id="d1", text="Paper 1"),
            IndexedDocument(id="d2", text="Paper 2"),
        ]
        index.add_documents(docs)
        assert index.count() == 2
        index.delete(["d1"])
        assert index.count() == 1

    def test_clear(self):
        backend = MockBackend()
        index = EmbeddingIndex(backend=backend, embedder=MockEmbedder())
        index.add_documents([IndexedDocument(id="d1", text="Paper")])
        assert index.count() == 1
        index.clear()
        assert index.count() == 0

    def test_search_without_embedder_raises(self):
        backend = MockBackend()
        index = EmbeddingIndex(backend=backend)
        with pytest.raises(ValueError, match="String queries require an embedder"):
            index.search("query string")

    def test_add_without_embedder_raises(self):
        backend = MockBackend()
        index = EmbeddingIndex(backend=backend)
        with pytest.raises(
            ValueError, match="Documents without pre-computed embeddings require an embedder"
        ):
            index.add_documents([IndexedDocument(id="d1", text="Paper")])

    def test_search_with_filters_empty_results(self):
        backend = MockBackend()
        index = EmbeddingIndex(backend=backend, embedder=MockEmbedder())
        docs = [
            IndexedDocument(id="d1", text="ML paper", metadata={"year": 2024}),
        ]
        index.add_documents(docs)
        results = index.search(
            [1.0, 0.0, 0.0, 0.0],
            top_k=10,
            filters=field("year", "eq", 2020),
        )
        assert len(results) == 0
