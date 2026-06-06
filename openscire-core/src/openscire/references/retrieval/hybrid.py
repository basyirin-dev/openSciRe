from __future__ import annotations

import logging

from openscire.references.indexing.index import EmbeddingIndex
from openscire.references.indexing.models import IndexedDocument, SearchResult
from openscire.references.indexing.reranker import CrossEncoderReranker
from openscire.references.retrieval.expansion import QueryExpander
from openscire.references.retrieval.fielded import FieldedSearchIndex
from openscire.references.retrieval.models import HybridRetrieverConfig
from openscire.references.retrieval.sparse import BM25SparseIndex

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(
        self,
        config: HybridRetrieverConfig | None = None,
        embedding_index: EmbeddingIndex | None = None,
        sparse_index: BM25SparseIndex | None = None,
        fielded_index: FieldedSearchIndex | None = None,
        reranker: CrossEncoderReranker | None = None,
        expander: QueryExpander | None = None,
    ) -> None:
        self.config = config or HybridRetrieverConfig()
        self._embedding_index = embedding_index
        self._sparse_index = sparse_index
        self._fielded_index = fielded_index
        self._reranker = reranker
        self._expander = expander or QueryExpander()

    def search(
        self,
        query: str,
        top_k: int | None = None,
        fields: list[str] | None = None,
    ) -> list[SearchResult]:
        k = top_k or self.config.top_k

        if not query or not query.strip():
            return []

        sparse_query = query
        if self.config.enable_query_expansion:
            variants = self._expander.expand(query)
            if len(variants) > 1:
                sparse_query = variants[1]
                logger.debug("Expanded query: %s -> %s", query, sparse_query)

        dense_results: list[SearchResult] = []
        if self._embedding_index is not None and self.config.dense_weight > 0:
            dense_input_top_k = k * 4
            try:
                dense_results = self._embedding_index.search(
                    query=query,
                    top_k=dense_input_top_k,
                )
            except Exception as e:
                logger.warning("Dense search failed: %s", e)

        sparse_results: list[SearchResult] = []
        if self.config.sparse_weight > 0:
            sparse_input_top_k = k * 4
            try:
                if self._fielded_index is not None:
                    sparse_results = self._fielded_index.search(
                        query=sparse_query,
                        top_k=sparse_input_top_k,
                        fields=fields,
                    )
                elif self._sparse_index is not None:
                    sparse_results = self._sparse_index.search(
                        query=sparse_query,
                        top_k=sparse_input_top_k,
                    )
            except Exception as e:
                logger.warning("Sparse search failed: %s", e)

        if not dense_results and not sparse_results:
            return []

        fused: list[SearchResult] = []
        if dense_results and sparse_results:
            fused = self._rrf_fuse(dense_results, sparse_results)
        elif dense_results:
            fused = dense_results
        elif sparse_results:
            fused = sparse_results

        if self.config.enable_reranking and self._reranker is not None and fused:
            try:
                fused = self._reranker.rerank(query, fused, self.config.rerank_top_k)
            except Exception as e:
                logger.warning("Reranking failed: %s", e)

        seen_ids: set[str] = set()
        final: list[SearchResult] = []
        rank = 1
        for r in fused:
            if r.document.id in seen_ids:
                continue
            seen_ids.add(r.document.id)
            r.rank = rank
            final.append(r)
            rank += 1
            if len(final) >= k:
                break

        return final

    def _rrf_fuse(
        self,
        dense: list[SearchResult],
        sparse: list[SearchResult],
    ) -> list[SearchResult]:
        k = self.config.rrf_k
        w_d = self.config.dense_weight
        w_s = self.config.sparse_weight
        scores: dict[str, float] = {}

        for rank, r in enumerate(dense):
            scores[r.document.id] = w_d / (k + rank + 1)

        for rank, r in enumerate(sparse):
            doc_id = r.document.id
            scores[doc_id] = scores.get(doc_id, 0.0) + w_s / (k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: -x[1])

        doc_map: dict[str, SearchResult] = {}
        for r in dense:
            doc_map[r.document.id] = r
        for r in sparse:
            if r.document.id not in doc_map:
                doc_map[r.document.id] = r

        results: list[SearchResult] = []
        for doc_id, score in ranked:
            if doc_id in doc_map:
                result = doc_map[doc_id]
                result.score = score
                results.append(result)

        return results

    def add_documents(self, documents: list[IndexedDocument]) -> None:
        if not documents:
            return

        if self._embedding_index is not None:
            try:
                self._embedding_index.add_documents(documents)
            except Exception as e:
                logger.warning("Failed to add documents to dense index: %s", e)

        if self._sparse_index is not None:
            try:
                self._sparse_index.add_documents(documents)
            except Exception as e:
                logger.warning("Failed to add documents to sparse index: %s", e)

        if self._fielded_index is not None:
            try:
                self._fielded_index.add_documents(documents)
            except Exception as e:
                logger.warning("Failed to add documents to fielded index: %s", e)
