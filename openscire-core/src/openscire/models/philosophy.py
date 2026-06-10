# SPDX-License-Identifier: Apache-2.0

"""Epistemic boundary and bias models (philosophy of science layer)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class BoundaryCategory(StrEnum):
    outside_corpus = "outside_corpus"
    unverifiable_assumptions = "unverifiable_assumptions"
    in_principle_unanswerable = "in_principle_unanswerable"
    confabulation_suspected = "confabulation_suspected"


class SourceCategory(StrEnum):
    public = "public"
    licensed = "licensed"
    irb_approved = "irb_approved"
    indigenous = "indigenous"
    clinical = "clinical"
    proprietary = "proprietary"


class KnowledgeBoundaryFlag(BaseModel):
    """Marks a query region outside the system's epistemic ken."""

    category: BoundaryCategory
    query: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    detail: str = ""
    requires_human_override: bool = True
    override_entry_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class EpistemicMarker(BaseModel):
    """Attaches provenance, bias, and confidence metadata to a knowledge claim."""

    source_category: SourceCategory
    source_type: str
    method: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    caveats: list[str] = Field(default_factory=list)
    corpus_bias: dict[str, object] = Field(default_factory=dict)
    provenance_entry_id: str | None = None
    reasoning_trace: str = ""
    source_language: str = ""
    funding_source: str | None = None


class FalsificationConfig(BaseModel):
    """Configures Popperian falsification logic for hypothesis testing."""

    enabled: bool = True
    auto_generate_null_hypotheses: bool = True
    require_falsifiability_check: bool = True
    block_non_verifiable_export: bool = True
    max_falsification_attempts: int = Field(default=3, ge=1)
    falsification_agent_temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    promote_to_not_falsified: bool = True
    negative_result_ttl_days: int = Field(default=365, gt=0)


class AgentTemperatureConfig(BaseModel):
    literature_review: float = Field(default=0.2, ge=0.0, le=2.0)
    hypothesis_generation: float = Field(default=0.9, ge=0.0, le=2.0)
    falsification: float = Field(default=0.8, ge=0.0, le=2.0)
    ethics: float = Field(default=0.3, ge=0.0, le=2.0)
    sandbox: float = Field(default=0.1, ge=0.0, le=2.0)


class AgentObjective(StrEnum):
    balanced = "balanced"
    skeptical = "skeptical"
    supportive = "supportive"
    novelty_seeking = "novelty_seeking"
    consensus_seeking = "consensus_seeking"


class AgentModelProvider(BaseModel):
    role: str
    provider: str = "ollama"
    model_name: str = "llama3.1"
    temperature: float | None = None
    objective_function: str = AgentObjective.balanced.value
    tool_access: list[str] = Field(default_factory=list)


_default_providers: list[AgentModelProvider] = [
    AgentModelProvider(role="literature_review", provider="ollama", model_name="llama3.1"),
    AgentModelProvider(role="hypothesis_generation", provider="ollama", model_name="llama3.1"),
    AgentModelProvider(role="falsification", provider="ollama", model_name="llama3.1"),
]


class AgentDiversityConfig(BaseModel):
    """Configures multi-agent diversity: serendipity, contradiction-driven
    exploration, and fallback cascades."""

    serendipity_level: float = Field(default=0.4, ge=0.0, le=1.0)
    enable_contradiction_driven_exploration: bool = True
    providers: list[AgentModelProvider] = Field(default_factory=lambda: _default_providers)
    temperature_defaults: AgentTemperatureConfig = AgentTemperatureConfig()
    fallback_cascade: list[str] = Field(
        default_factory=lambda: ["local", "cheaper_local", "byok", "fail"]
    )
