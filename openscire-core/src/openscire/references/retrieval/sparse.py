from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter

from openscire.references.indexing.models import IndexedDocument, SearchResult

logger = logging.getLogger(__name__)

_WORD_TOKENIZE = re.compile(r"\w+")


class BM25SparseIndex:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._doc_texts: dict[str, str] = {}
        self._doc_metadatas: dict[str, dict] = {}
        self._doc_lengths: dict[str, int] = {}
        self._avgdl: float = 0.0
        self._doc_count: int = 0
        self._inverted_index: dict[str, dict[str, int]] = {}
        self._idf_cache: dict[str, float] = {}

    def add_documents(self, documents: list[IndexedDocument]) -> None:
        if not documents:
            return

        doc_ids_added: list[str] = []
        for doc in documents:
            tokens = _WORD_TOKENIZE.findall(doc.text.lower())
            if not tokens:
                continue
            self._doc_texts[doc.id] = doc.text
            if doc.metadata:
                self._doc_metadatas[doc.id] = doc.metadata
            self._doc_lengths[doc.id] = len(tokens)
            doc_ids_added.append(doc.id)

            term_counts = Counter(tokens)
            for term, count in term_counts.items():
                if term not in self._inverted_index:
                    self._inverted_index[term] = {}
                self._inverted_index[term][doc.id] = count

        if doc_ids_added:
            self._doc_count += len(doc_ids_added)
            self._avgdl = (
                sum(self._doc_lengths.values()) / self._doc_count
                if self._doc_count > 0
                else 0.0
            )
            self._idf_cache.clear()

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[SearchResult]:
        if self._doc_count == 0 or not query.strip():
            return []

        query_tokens = _WORD_TOKENIZE.findall(query.lower())
        if not query_tokens:
            return []

        scores: dict[str, float] = {}
        query_term_counts = Counter(query_tokens)

        for term, qtf in query_term_counts.items():
            if term not in self._inverted_index:
                continue
            idf = self._get_idf(term)
            posting = self._inverted_index[term]

            for doc_id, tf in posting.items():
                doc_len = self._doc_lengths[doc_id]
                numerator = tf * (self._k1 + 1)
                denominator = tf + self._k1 * (
                    1 - self._b + self._b * doc_len / self._avgdl
                )
                scores[doc_id] = scores.get(doc_id, 0.0) + qtf * idf * numerator / denominator

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        ranked = ranked[:top_k]

        results: list[SearchResult] = []
        for i, (doc_id, score) in enumerate(ranked):
            text = self._doc_texts.get(doc_id, "")
            meta = self._doc_metadatas.get(doc_id, {})
            results.append(
                SearchResult(
                    document=IndexedDocument(id=doc_id, text=text, metadata=meta),
                    score=score,
                    rank=i + 1,
                )
            )

        return results

    def _get_idf(self, term: str) -> float:
        if term in self._idf_cache:
            return self._idf_cache[term]
        n = len(self._inverted_index.get(term, {}))
        idf = math.log((self._doc_count - n + 0.5) / (n + 0.5) + 1.0)
        self._idf_cache[term] = idf
        return idf

    def save(self, path: str) -> None:
        data = {
            "k1": self._k1,
            "b": self._b,
            "avgdl": self._avgdl,
            "doc_count": self._doc_count,
            "doc_texts": self._doc_texts,
            "doc_metadatas": self._doc_metadatas,
            "doc_lengths": self._doc_lengths,
            "inverted_index": self._inverted_index,
            "idf_cache": self._idf_cache,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path: str) -> None:
        with open(path) as f:
            data = json.load(f)
        self._k1 = data["k1"]
        self._b = data["b"]
        self._avgdl = data["avgdl"]
        self._doc_count = data["doc_count"]
        self._doc_texts = data["doc_texts"]
        self._doc_metadatas = data.get("doc_metadatas", {})
        self._doc_lengths = data["doc_lengths"]
        self._inverted_index = data["inverted_index"]
        self._idf_cache = data.get("idf_cache", {})

    def clear(self) -> None:
        self._doc_texts.clear()
        self._doc_metadatas.clear()
        self._doc_lengths.clear()
        self._inverted_index.clear()
        self._idf_cache.clear()
        self._avgdl = 0.0
        self._doc_count = 0

    def count(self) -> int:
        return self._doc_count
