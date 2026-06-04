from __future__ import annotations

import logging
from typing import Any

from openscire.references.indexing.models import SearchResult

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None  # noqa: ANN401
        self._available: bool | None = None

    def _lazy_init(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)
            self._available = True
            logger.info("Loaded cross-encoder model %s", self._model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not available — cross-encoder reranking disabled"
            )
            self._available = False
        except Exception as e:
            logger.warning("Failed to load cross-encoder model %s: %s", self._model_name, e)
            self._available = False
        return self._available

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 10,
    ) -> list[SearchResult]:
        if not results:
            return []
        if not self._lazy_init():
            return results[:top_k]
        try:
            pairs = [(query, r.document.text) for r in results]
            scores = self._model.predict(pairs)
            scored = list(zip(results, scores, strict=False))
            scored.sort(key=lambda x: x[1], reverse=True)
            reranked: list[SearchResult] = []
            for i, (r, s) in enumerate(scored[:top_k]):
                r.rerank_score = float(s)
                r.rank = i + 1
                reranked.append(r)
            return reranked
        except Exception as e:
            logger.warning("Cross-encoder reranking failed: %s", e)
            return results[:top_k]
