from __future__ import annotations

import logging
from typing import Any

from openscire.references.indexing.backends import VectorBackend
from openscire.references.indexing.filters import evaluate as eval_filters
from openscire.references.indexing.filters import FilterExpression
from openscire.references.indexing.models import IndexedDocument, SearchResult

logger = logging.getLogger(__name__)


class EmbeddingIndex:
    def __init__(
        self,
        backend: VectorBackend,
        embedder: Any | None = None,  # noqa: ANN401
    ) -> None:
        self._backend = backend
        self._embedder = embedder

    def add_documents(
        self,
        documents: list[IndexedDocument],
        batch_size: int = 32,
    ) -> None:
        if not documents:
            return
        texts: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for doc in documents:
            if doc.embedding is not None:
                self._backend.add([doc.id], [doc.embedding], [doc.metadata])
            else:
                texts.append(doc.text)
                ids.append(doc.id)
                metadatas.append(doc.metadata)
        if texts and self._embedder is not None:
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i : i + batch_size]
                batch_ids = ids[i : i + batch_size]
                batch_metas = metadatas[i : i + batch_size]
                vectors = self._embedder.encode(batch_texts)
                self._backend.add(batch_ids, vectors, batch_metas)
                logger.debug("Indexed batch %d/%d", i // batch_size + 1, (len(texts) - 1) // batch_size + 1)
        elif texts and self._embedder is None:
            raise ValueError(
                "Documents without pre-computed embeddings require an embedder"
            )

    async def add_documents_async(
        self,
        documents: list[IndexedDocument],
        batch_size: int = 32,
    ) -> None:
        if not documents:
            return
        texts: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        pre_embedded: list[tuple[str, list[float], dict]] = []
        for doc in documents:
            if doc.embedding is not None:
                pre_embedded.append((doc.id, doc.embedding, doc.metadata))
            else:
                texts.append(doc.text)
                ids.append(doc.id)
                metadatas.append(doc.metadata)
        if pre_embedded:
            p_ids, p_vecs, p_metas = zip(*pre_embedded, strict=False)
            self._backend.add(list(p_ids), list(p_vecs), list(p_metas))
        if texts and self._embedder is not None:
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i : i + batch_size]
                batch_ids = ids[i : i + batch_size]
                batch_metas = metadatas[i : i + batch_size]
                vectors = self._embedder.encode(batch_texts)
                self._backend.add(batch_ids, vectors, batch_metas)
        elif texts and self._embedder is None:
            raise ValueError(
                "Documents without pre-computed embeddings require an embedder"
            )

    def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
        reranker: Any | None = None,  # noqa: ANN401
    ) -> list[SearchResult]:
        if isinstance(query, str):
            if self._embedder is None:
                raise ValueError("String queries require an embedder")
            query_vector = self._embedder.encode_query(query)
        else:
            query_vector = query
        results = self._backend.search(query_vector, top_k=top_k * 4)
        filtered: list[tuple[str, float, dict[str, Any]]] = [
            (doc_id, score, meta)
            for doc_id, score, meta in results
            if eval_filters(filters, meta)
        ]
        filtered.sort(key=lambda x: x[1], reverse=True)
        filtered = filtered[:top_k]
        search_results = [
            SearchResult(
                document=IndexedDocument(
                    id=doc_id,
                    text="",
                    metadata=meta,
                ),
                score=score,
                rank=i + 1,
            )
            for i, (doc_id, score, meta) in enumerate(filtered)
        ]
        if reranker is not None and isinstance(query, str):
            try:
                search_results = reranker.rerank(query, search_results, top_k)
            except Exception as e:
                logger.warning("Reranking failed: %s", e)
        return search_results

    def delete(self, ids: list[str]) -> None:
        self._backend.delete(ids)

    def count(self) -> int:
        return self._backend.count()

    def save(self, path: str) -> None:
        self._backend.save(path)

    def load(self, path: str) -> None:
        self._backend.load(path)

    def clear(self) -> None:
        self._backend.clear()
