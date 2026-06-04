from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from openscire.references.models import ReferenceItem


class SourceProvenance(StrEnum):
    user_provided = "user_provided"
    externally_retrieved = "externally_retrieved"


class AdversarialSource(BaseModel):
    claim: str = ""
    source: ReferenceItem | None = None
    contradiction_type: str = ""
    retrieved_via: str = ""
    confidence: float = 0.0


class Assumption(BaseModel):
    assumption_text: str
    extracted_from: str = ""
    domain: str = ""
    supporting_sources: list[ReferenceItem] = Field(default_factory=list)
    contradicting_sources: list[ReferenceItem] = Field(default_factory=list)


class SourceQualityScore(BaseModel):
    source_id: str
    overall_score: float = 0.0
    methodology_score: float = 0.0
    replication_score: float = 0.0
    citation_score: float = 0.0
    recency_score: float = 0.0


class EchoChamberReport(BaseModel):
    external_ratio: float = 0.0
    external_ratio_pass: bool = False
    n_user_sources: int = 0
    n_external_sources: int = 0
    n_contradictory_sources: int = 0
    assumptions: list[Assumption] = Field(default_factory=list)
    adversarial_sources: list[AdversarialSource] = Field(default_factory=list)
    confidence_ranked_sources: list[SourceQualityScore] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config: dict[str, Any] = Field(default_factory=dict)
