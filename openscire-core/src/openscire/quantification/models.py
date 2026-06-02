from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceQuality(StrEnum):
    PEER_REVIEWED = "peer_reviewed"
    PREPRINT = "preprint"
    GRAY_LITERATURE = "gray_literature"
    ANECDOTAL = "anecdotal"
    UNKNOWN = "unknown"


class ContradictionType(StrEnum):
    DIRECT = "direct"
    NUANCED = "nuanced"
    METHODOLOGICAL = "methodological"


class ClaimConfidence(BaseModel):
    claim_text: str
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    agreement_score: float = Field(default=0.0, ge=0.0, le=1.0)
    model_confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_density_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_count: int = 0
    contradictory_count: int = 0
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    timestamp: datetime = Field(default_factory=datetime.now)


class Contradiction(BaseModel):
    claim_a: str
    claim_b: str
    contradiction_type: ContradictionType = ContradictionType.DIRECT
    severity: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_a: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_b: float = Field(default=0.0, ge=0.0, le=1.0)
    resolution: str = ""


class KnowledgeBoundary(BaseModel):
    query: str
    category: str = "outside_corpus"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    detail: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class ModelUncertainty(BaseModel):
    available: bool = False
    mean_logprob: float = 0.0
    perplexity: float = 0.0
    entropy: float = 0.0
    refusal_detected: bool = False
    refusal_pattern: str = ""


class UncertaintyReport(BaseModel):
    claims: list[ClaimConfidence] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    boundaries: list[KnowledgeBoundary] = Field(default_factory=list)
    model_uncertainty: ModelUncertainty | None = None
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DisclosedClaim(BaseModel):
    claim: str
    confidence: ClaimConfidence = Field(default_factory=lambda: ClaimConfidence(claim_text=""))
    disclosure: str = ""
