from __future__ import annotations

import logging
from typing import Any

from openscire.references.indexing.models import IndexedDocument, SearchResult
from openscire.references.retrieval.sparse import BM25SparseIndex

logger = logging.getLogger(__name__)

_FIELD_KEYS = ["title", "abstract", "methods", "body", "results", "discussion", "conclusion"]


class FieldedSearchIndex:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._fulltext_index = BM25SparseIndex(k1=k1, b=b)
        self._field_indices: dict[str, BM25SparseIndex] = {}
        self._field_metadata: dict[str, set[str]] = {}
        self._documents: list[IndexedDocument] = []
        self._has_field: dict[str, set[str]] = {}
        self._built_fields: set[str] = set()

    def add_documents(self, documents: list[IndexedDocument]) -> None:
        self._fulltext_index.add_documents(documents)
        self._documents.extend(documents)

        for doc in documents:
            meta = doc.metadata or {}
            for field_key in _FIELD_KEYS:
                if (
                    field_key in meta
                    and isinstance(meta[field_key], str)
                    and meta[field_key].strip()
                ):
                    if field_key not in self._has_field:
                        self._has_field[field_key] = set()
                    self._has_field[field_key].add(doc.id)

    def search(
        self,
        query: str,
        top_k: int = 10,
        fields: list[str] | None = None,
    ) -> list[SearchResult]:
        if not fields or "full_text" in fields:
            return self._fulltext_index.search(query, top_k=top_k)

        valid_fields = [f for f in fields if f in _FIELD_KEYS]
        if not valid_fields:
            return self._fulltext_index.search(query, top_k=top_k)

        all_scores: dict[str, float] = {}
        for field in valid_fields:
            field_results = self._search_field(field, query, top_k)
            for r in field_results:
                doc_id = r.document.id
                all_scores[doc_id] = all_scores.get(doc_id, 0.0) + 1.0 / (
                    60 + r.rank
                )

        ranked = sorted(all_scores.items(), key=lambda x: -x[1])
        ranked = ranked[:top_k]

        seen_ids = set()
        results: list[SearchResult] = []
        rank = 1
        for doc_id, _score in ranked:
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            text = ""
            meta: dict[str, Any] = {}
            for doc in self._documents:
                if doc.id == doc_id:
                    text = doc.text
                    meta = doc.metadata
                    break
            results.append(
                SearchResult(
                    document=IndexedDocument(id=doc_id, text=text, metadata=meta),
                    score=_score,
                    rank=rank,
                )
            )
            rank += 1

        return results

    def _search_field(
        self,
        field: str,
        query: str,
        top_k: int,
    ) -> list[SearchResult]:
        if field not in self._built_fields:
            self._build_field_index(field)
        field_idx = self._field_indices.get(field)
        if field_idx is None or field_idx.count() == 0:
            return []
        return field_idx.search(query, top_k=top_k)

    def _build_field_index(self, field: str) -> None:
        if field in self._built_fields:
            return
        if field not in self._has_field:
            self._built_fields.add(field)
            return

        field_docs: list[IndexedDocument] = []
        doc_ids_with_field = self._has_field.get(field, set())

        for doc in self._documents:
            if doc.id in doc_ids_with_field:
                meta = doc.metadata or {}
                field_text = meta.get(field, "")
                if isinstance(field_text, str) and field_text.strip():
                    field_docs.append(
                        IndexedDocument(
                            id=doc.id,
                            text=field_text,
                            metadata=meta,
                        )
                    )

        if field_docs:
            field_idx = BM25SparseIndex(k1=self._k1, b=self._b)
            field_idx.add_documents(field_docs)
            self._field_indices[field] = field_idx
            logger.debug("Built BM25 index for field '%s' with %d docs", field, len(field_docs))

        self._built_fields.add(field)

    def count(self) -> int:
        return self._fulltext_index.count()

    def clear(self) -> None:
        self._fulltext_index.clear()
        self._field_indices.clear()
        self._has_field.clear()
        self._built_fields.clear()
        self._documents.clear()
