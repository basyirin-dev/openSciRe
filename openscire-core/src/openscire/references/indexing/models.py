from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IndexedDocument(BaseModel):
    id: str
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class SearchResult(BaseModel):
    document: IndexedDocument
    score: float = 0.0
    rank: int = 0
    rerank_score: float | None = None
