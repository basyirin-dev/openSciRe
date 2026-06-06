from __future__ import annotations

from pydantic import BaseModel


class HybridRetrieverConfig(BaseModel):
    top_k: int = 10
    dense_weight: float = 1.0
    sparse_weight: float = 1.0
    rrf_k: int = 60
    rerank_top_k: int = 5
    enable_query_expansion: bool = False
    enable_reranking: bool = False
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
