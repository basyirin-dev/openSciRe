# SPDX-License-Identifier: Apache-2.0

"""Multilingual embedding model support (LaBSE, multilingual E5, BGE-M3).

Provides cross-lingual semantic search using sentence-transformers models
that understand 100+ languages.  Models are downloaded on first use.

Optional dependency: sentence-transformers (install with pip).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MultilingualEmbedder:
    """Local multilingual embedding service.

    Wraps sentence-transformers to compute cross-lingual embeddings
    for semantic search across languages.  Supports LaBSE (109 langs),
    multilingual E5 (100 langs), and BGE-M3 (100+ langs).

    Models are downloaded from HuggingFace on first encode() call.
    Requires: pip install sentence-transformers

    Usage:
        embedder = MultilingualEmbedder(model_name="labse")
        vecs = embedder.encode(["Hola mundo", "Hello world"])
        sim = embedder.similarity(vecs[0], vecs[1])
    """

    SUPPORTED_MODELS: dict[str, str] = {
        "labse": "sentence-transformers/LaBSE",
        "mE5-large": "intfloat/multilingual-e5-large",
        "bge-m3": "BAAI/bge-m3",
    }

    def __init__(self, model_name: str = "labse") -> None:
        if model_name not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model '{model_name}'. Choose from: {', '.join(self.SUPPORTED_MODELS)}"
            )
        self._model_name = model_name
        self._model_key = model_name
        self._model: Any = None  # noqa: ANN401

    def _lazy_init(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            hf_name = self.SUPPORTED_MODELS[self._model_key]
            self._model = SentenceTransformer(hf_name)
            logger.info(
                "Loaded multilingual model %s (%s)",
                self._model_key,
                hf_name,
            )
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for MultilingualEmbedder. "
                "Install with: pip install sentence-transformers"
            ) from None
        except Exception as e:
            raise RuntimeError(f"Failed to load model {self._model_key}: {e}") from e

    def encode(
        self,
        texts: list[str],
        normalize: bool = True,
    ) -> list[list[float]]:
        """Encode a list of texts into embedding vectors.

        Args:
            texts: List of text strings to encode.
            normalize: Whether to L2-normalize the embeddings.

        Returns:
            List of embedding vectors as list[float].
        """
        self._lazy_init()
        if not texts:
            return []
        import torch

        with torch.no_grad():
            if self._model_key == "mE5-large":
                prefixed = [f"query: {t}" if len(texts) == 1 else f"passage: {t}" for t in texts]
                embeddings = self._model.encode(prefixed, normalize_embeddings=normalize)
            else:
                embeddings = self._model.encode(texts, normalize_embeddings=normalize)
        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()  # type: ignore[no-any-return]
        return list(embeddings)

    def encode_query(self, query: str) -> list[float]:
        """Encode a single query string for retrieval.

        For E5 models, this automatically prepends the "query: " prefix.
        """
        vecs = self.encode([query], normalize=True)
        return vecs[0] if vecs else []

    @staticmethod
    @staticmethod
    def similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two embedding vectors."""
        dot: float = sum(x * y for x, y in zip(a, b, strict=False))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)  # type: ignore[no-any-return]

    def cross_lingual_retrieve(
        self,
        query: str,
        candidates: list[Any],  # noqa: ANN401
        query_embedding: list[float] | None = None,
        top_k: int = 10,
    ) -> list[tuple[Any, float]]:  # noqa: ANN401
        """Retrieve top-k items by cross-lingual similarity.

        Args:
            query: Search query (will be encoded if query_embedding not provided).
            candidates: List of (text, item) tuples or objects with a text-like attribute.
            query_embedding: Pre-computed query embedding (optional).
            top_k: Number of results to return.

        Returns:
            List of (item, score) tuples sorted by similarity descending.
        """
        query_vec = self.encode_query(query) if query_embedding is None else query_embedding

        if not candidates:
            return []

        texts = []
        mapping: dict[int, Any] = {}
        for i, c in enumerate(candidates):
            if isinstance(c, tuple):
                texts.append(str(c[0]))
                mapping[i] = c[1]
            else:
                texts.append(str(c))
                mapping[i] = c

        candidate_vecs = self.encode(texts, normalize=True)
        scored: list[tuple[int, float]] = [
            (i, self.similarity(query_vec, cv)) for i, cv in enumerate(candidate_vecs)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(mapping[i], score) for i, score in scored[:top_k]]

    @property
    def model_languages(self) -> int:
        """Approximate number of languages supported by the model."""
        lang_map = {
            "labse": 109,
            "mE5-large": 100,
            "bge-m3": 100,
        }
        return lang_map.get(self._model_key, 0)

    @property
    def embedding_dimension(self) -> int:
        """Return the embedding dimension for the loaded model."""
        self._lazy_init()
        return self._model.get_sentence_embedding_dimension()  # type: ignore[no-any-return]
