import tempfile
from typing import Any

from openscire.references.indexing.index import EmbeddingIndex
from openscire.references.indexing.models import IndexedDocument
from openscire.references.retrieval import (
    BM25SparseIndex,
    FieldedSearchIndex,
    HybridRetriever,
    HybridRetrieverConfig,
    QueryExpander,
)


class MockBackend:
    def __init__(self) -> None:
        self._data: dict[str, tuple[list[float], dict]] = {}

    def add(  # noqa: ANN201
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        for i, doc_id in enumerate(ids):
            self._data[doc_id] = (
                vectors[i],
                metadatas[i] if metadatas else {},
            )

    def search(  # noqa: ANN201
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        import numpy as np

        query = np.array(query_vector)
        query = query / (np.linalg.norm(query) + 1e-10)
        scored: list[tuple[str, float, dict[str, Any]]] = []
        for doc_id, (vec, meta) in self._data.items():
            v = np.array(vec)
            v = v / (np.linalg.norm(v) + 1e-10)
            score = float(np.dot(query, v))
            scored.append((doc_id, score, meta))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def delete(self, ids: list[str]) -> None:  # noqa: ANN201
        for doc_id in ids:
            self._data.pop(doc_id, None)

    def count(self) -> int:  # noqa: ANN201
        return len(self._data)

    def save(self, path: str) -> None:  # noqa: ANN201
        pass

    def load(self, path: str) -> None:  # noqa: ANN201
        pass

    def clear(self) -> None:  # noqa: ANN201
        self._data.clear()


class MockEmbedder:
    def encode(self, texts: list[str]) -> list[list[float]]:  # noqa: ANN201
        import hashlib

        result: list[list[float]] = []
        for t in texts:
            h = hashlib.md5(t.encode()).digest()
            vec = [b / 255.0 for b in h[:4]]
            result.append(vec)
        return result

    def encode_query(self, query: str) -> list[float]:  # noqa: ANN201
        return self.encode([query])[0]


# =============================================================================
# BM25SparseIndex tests
# =============================================================================


class TestBM25SparseIndex:
    def test_add_and_search(self) -> None:
        index = BM25SparseIndex()
        docs = [
            IndexedDocument(id="a", text="Machine learning for biology"),
            IndexedDocument(id="b", text="Biology research methods"),
            IndexedDocument(id="c", text="Physics theory and mathematics"),
        ]
        index.add_documents(docs)
        assert index.count() == 3

        results = index.search("biology", top_k=5)
        assert len(results) >= 2
        assert any(r.document.id == "a" for r in results)
        assert any(r.document.id == "b" for r in results)

    def test_empty_index_returns_empty(self) -> None:
        index = BM25SparseIndex()
        results = index.search("anything", top_k=10)
        assert len(results) == 0

    def test_save_and_load(self) -> None:
        index = BM25SparseIndex()
        docs = [
            IndexedDocument(id="x", text="DNA sequencing methods"),
            IndexedDocument(id="y", text="PCR amplification protocol"),
        ]
        index.add_documents(docs)

        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            index.save(f.name)
            loaded = BM25SparseIndex()
            loaded.load(f.name)

        assert loaded.count() == 2
        results = loaded.search("dna", top_k=5)
        assert len(results) >= 1

    def test_clear(self) -> None:
        index = BM25SparseIndex()
        index.add_documents([IndexedDocument(id="d", text="Some text")])
        assert index.count() == 1
        index.clear()
        assert index.count() == 0

    def test_search_ranking(self) -> None:
        index = BM25SparseIndex()
        docs = [
            IndexedDocument(id="dna_doc", text="DNA DNA DNA DNA DNA DNA"),
            IndexedDocument(id="once_doc", text="DNA is mentioned once here"),
        ]
        index.add_documents(docs)
        results = index.search("DNA", top_k=5)
        assert len(results) == 2
        assert results[0].document.id == "dna_doc"


# =============================================================================
# FieldedSearchIndex tests
# =============================================================================


class TestFieldedSearchIndex:
    def test_field_detection_and_search(self) -> None:
        fielded = FieldedSearchIndex()
        docs = [
            IndexedDocument(
                id="d1",
                text="Full text about PCR methods and protocols",
                metadata={
                    "title": "PCR Methods",
                    "abstract": "We developed new PCR protocols",
                },
            ),
            IndexedDocument(
                id="d2",
                text="Biology research paper on DNA",
                metadata={
                    "title": "DNA Research",
                    "abstract": "This paper studies DNA",
                },
            ),
        ]
        fielded.add_documents(docs)

        results = fielded.search("PCR", top_k=5, fields=["title"])
        assert len(results) >= 1
        assert results[0].document.id == "d1"

    def test_lazy_field_index_built_on_demand(self) -> None:
        fielded = FieldedSearchIndex()
        docs = [
            IndexedDocument(
                id="d1",
                text="Cancer research full text",
                metadata={"title": "Cancer Study", "abstract": "Abstract about cancer"},
            ),
        ]
        fielded.add_documents(docs)

        assert "title" not in fielded._built_fields
        results = fielded.search("cancer", top_k=5, fields=["title"])
        assert len(results) >= 1
        assert "title" in fielded._built_fields

    def test_multi_field_search(self) -> None:
        fielded = FieldedSearchIndex()
        docs = [
            IndexedDocument(
                id="d1",
                text="Full text about something else",
                metadata={
                    "title": "Cancer Biology",
                    "abstract": "Abstract text",
                },
            ),
            IndexedDocument(
                id="d2",
                text="Another full text",
                metadata={
                    "title": "Something Else",
                    "abstract": "This abstract discusses cancer mechanisms",
                },
            ),
        ]
        fielded.add_documents(docs)

        results = fielded.search("cancer", top_k=5, fields=["title", "abstract"])
        assert len(results) >= 2

    def test_fallback_to_fulltext(self) -> None:
        fielded = FieldedSearchIndex()
        docs = [
            IndexedDocument(id="d1", text="Machine learning approaches"),
        ]
        fielded.add_documents(docs)

        results = fielded.search("machine", top_k=5, fields=["full_text"])
        assert len(results) >= 1

    def test_empty_fields_fallback_to_fulltext(self) -> None:
        fielded = FieldedSearchIndex()
        docs = [
            IndexedDocument(id="d1", text="Some text about biology"),
        ]
        fielded.add_documents(docs)

        results = fielded.search("biology", top_k=5, fields=[])
        assert len(results) >= 1


# =============================================================================
# QueryExpander tests
# =============================================================================


class TestQueryExpander:
    def test_builtin_synonyms(self) -> None:
        expander = QueryExpander()
        variants = expander.expand("PCR amplification")
        assert len(variants) >= 2
        assert "PCR amplification" in variants
        assert any("polymerase chain reaction" in v.lower() for v in variants)

    def test_custom_synonyms_merged(self) -> None:
        expander = QueryExpander(custom_dict={"pcr": ["pcr test"]})
        variants = expander.expand("PCR protocol")
        assert any("pcr test" in v.lower() for v in variants)

    def test_empty_query(self) -> None:
        expander = QueryExpander()
        variants = expander.expand("")
        assert len(variants) == 0

    def test_no_expansion_needed(self) -> None:
        expander = QueryExpander()
        variants = expander.expand("quantum computing")
        assert len(variants) == 1
        assert variants[0] == "quantum computing"


# =============================================================================
# HybridRetriever tests
# =============================================================================


class TestHybridRetriever:
    def test_sparse_only_search(self) -> None:
        config = HybridRetrieverConfig(dense_weight=0.0, sparse_weight=1.0)
        sparse = BM25SparseIndex()
        sparse.add_documents(
            [
                IndexedDocument(id="a", text="Biology of DNA replication"),
                IndexedDocument(id="b", text="Physics of quantum mechanics"),
            ]
        )
        retriever = HybridRetriever(config=config, sparse_index=sparse)
        results = retriever.search("DNA", top_k=5)
        assert len(results) >= 1
        assert results[0].document.id == "a"

    def test_dense_only_search(self) -> None:
        config = HybridRetrieverConfig(dense_weight=1.0, sparse_weight=0.0)
        backend = MockBackend()
        embedding_index = EmbeddingIndex(backend=backend, embedder=MockEmbedder())
        docs = [
            IndexedDocument(id="a", text="Machine learning biology"),
            IndexedDocument(id="b", text="Physics paper"),
        ]
        embedding_index.add_documents(docs)
        retriever = HybridRetriever(config=config, embedding_index=embedding_index)
        results = retriever.search("biology", top_k=5)
        assert len(results) >= 1

    def test_hybrid_fusion(self) -> None:
        config = HybridRetrieverConfig(dense_weight=1.0, sparse_weight=1.0)
        backend = MockBackend()
        embedding_index = EmbeddingIndex(backend=backend, embedder=MockEmbedder())
        docs = [
            IndexedDocument(id="a", text="DNA sequencing techniques"),
            IndexedDocument(id="b", text="PCR amplification for DNA"),
            IndexedDocument(id="c", text="Quantum physics theory"),
        ]
        embedding_index.add_documents(docs)

        sparse = BM25SparseIndex()
        sparse.add_documents(
            [
                IndexedDocument(id="a", text="DNA sequencing techniques"),
                IndexedDocument(id="b", text="PCR amplification for DNA"),
                IndexedDocument(id="c", text="Quantum physics theory"),
            ]
        )

        retriever = HybridRetriever(
            config=config, embedding_index=embedding_index, sparse_index=sparse
        )
        results = retriever.search("DNA sequencing", top_k=3)
        assert len(results) >= 2
        assert results[0].document.id in ("a", "b")

    def test_empty_query_returns_empty(self) -> None:
        retriever = HybridRetriever()
        results = retriever.search("", top_k=10)
        assert len(results) == 0

    def test_config_top_k_respected(self) -> None:
        config = HybridRetrieverConfig(top_k=1, dense_weight=0.0, sparse_weight=1.0)
        sparse = BM25SparseIndex()
        sparse.add_documents(
            [
                IndexedDocument(id="a", text="DNA research"),
                IndexedDocument(id="b", text="DNA sequencing"),
            ]
        )
        retriever = HybridRetriever(config=config, sparse_index=sparse)
        results = retriever.search("DNA", top_k=1)
        assert len(results) == 1

    def test_fielded_search_via_sparse(self) -> None:
        config = HybridRetrieverConfig(dense_weight=0.0, sparse_weight=1.0)
        fielded = FieldedSearchIndex()
        fielded.add_documents(
            [
                IndexedDocument(
                    id="d1",
                    text="Full text about general biology",
                    metadata={"title": "Cancer Biology", "abstract": "Abstract text"},
                ),
                IndexedDocument(
                    id="d2",
                    text="Another article on physics",
                    metadata={
                        "title": "Physics Today",
                        "abstract": "Discusses cancer in abstract",
                    },
                ),
            ]
        )
        retriever = HybridRetriever(config=config, fielded_index=fielded)
        results = retriever.search("cancer", top_k=5, fields=["title"])
        assert len(results) >= 1
        assert results[0].document.id == "d1"

    def test_dense_and_sparse_both_disabled_returns_empty(self) -> None:
        config = HybridRetrieverConfig(dense_weight=0.0, sparse_weight=0.0)
        retriever = HybridRetriever(config=config)
        results = retriever.search("anything", top_k=10)
        assert len(results) == 0

    def test_add_documents(self) -> None:
        config = HybridRetrieverConfig(dense_weight=0.0, sparse_weight=1.0)
        sparse = BM25SparseIndex()
        retriever = HybridRetriever(config=config, sparse_index=sparse)
        retriever.add_documents(
            [
                IndexedDocument(id="x", text="DNA replication"),
                IndexedDocument(id="y", text="RNA transcription"),
            ]
        )
        assert sparse.count() == 2
        results = retriever.search("DNA", top_k=5)
        assert len(results) >= 1
