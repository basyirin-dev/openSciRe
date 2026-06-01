# SPDX-License-Identifier: Apache-2.0

"""Core domain models for scientific claims, hypotheses, and provenance."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class VerificationStatus(StrEnum):
    unverified = "unverified"
    supported = "supported"
    contradicted = "contradicted"
    inconclusive = "inconclusive"
    retracted = "retracted"


class EvidenceType(StrEnum):
    experimental = "experimental"
    computational = "computational"
    literature = "literature"
    anecdotal = "anecdotal"


class ReproducibilityStatus(StrEnum):
    not_assessed = "not_assessed"
    reproduced = "reproduced"
    failed_to_reproduce = "failed_to_reproduce"
    not_reproducible = "not_reproducible"
    pending = "pending"


class HypothesisStatus(StrEnum):
    proposed = "proposed"
    tested = "tested"
    supported = "supported"
    refuted = "refuted"


class ScientificClaim(BaseModel):
    """A scientific claim with evidence chain, confidence, and verification status."""

    field: str
    evidence_chain: list[str] = Field(default_factory=list)
    confidence_interval: tuple[float, float] | None = None
    source_references: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.unverified
    timestamp: datetime = Field(default_factory=datetime.now)
    created_by: str = ""


class Evidence(BaseModel):
    """A piece of evidence supporting or contradicting a claim."""

    type: EvidenceType
    source: str
    strength_rating: float | None = None
    reproducibility_status: ReproducibilityStatus = ReproducibilityStatus.not_assessed
    date_collected: datetime = Field(default_factory=datetime.now)


class Hypothesis(BaseModel):
    """A testable hypothesis with falsification criteria and status."""

    claim: str
    null_hypothesis: str | None = None
    falsification_criteria: list[str] = Field(default_factory=list)
    testability_score: float | None = None
    domain_tags: list[str] = Field(default_factory=list)
    related_literature: list[str] = Field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.proposed


class ProvenanceEntry(BaseModel):
    """A single auditable action in the provenance DAG."""

    action_id: str
    action_type: str = ""
    parent_ids: list[str] = Field(default_factory=list)
    agent_id: str = ""
    model_id: str = ""
    parameters_snapshot: dict[str, object] = Field(default_factory=dict)
    input_hash: str = ""
    output_hash: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    cryptographic_signature: str | None = None


class LiteratureReference(BaseModel):
    """A reference to a scientific publication with metadata."""

    doi: str = ""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    journal: str = ""
    year: int | None = None
    citation_count: int = 0
    retraction_status: str = ""
    source_repository: str = ""
    full_text_hash: str | None = None


class ResearchContext(BaseModel):
    """The scope and constraints of a research project."""

    research_question: str = ""
    domain: str = ""
    hypotheses_in_scope: list[str] = Field(default_factory=list)
    literature_seed: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    ethical_flags: list[str] = Field(default_factory=list)
    project_id: str = ""


class ReproducibilityBundle(BaseModel):
    """Environment snapshot for reproducing research results."""

    environment_lockfile: str = ""
    dependency_tree: dict[str, str] = Field(default_factory=dict)
    config_snapshot: dict[str, object] = Field(default_factory=dict)
    random_seeds: dict[str, int] = Field(default_factory=dict)
    data_hashes: dict[str, str] = Field(default_factory=dict)
    hardware_profile: str = ""
