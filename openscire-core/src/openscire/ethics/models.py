from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from openscire.constants import DURCCategory, RiskTier
from openscire.models.philosophy import KnowledgeBoundaryFlag
from openscire.quantification.models import Contradiction


class FirewallAction(StrEnum):
    """Action taken when a DURC rule is triggered."""

    FLAG = "flag"
    WARN = "warn"
    BLOCK = "block"
    ESCALATE = "escalate"


class ScanLevel(StrEnum):
    """Which side of the LLM interaction to scan."""

    PROMPT = "prompt"
    RESPONSE = "response"
    BOTH = "both"


class MatchType(StrEnum):
    """How a DURC pattern was detected."""

    KEYWORD = "keyword"
    EMBEDDING = "embedding"
    LLM = "llm"


class FirewallRule(BaseModel):
    """A single ethical firewall rule binding a DURC category to a scan strategy."""

    id: str
    name: str
    category: DURCCategory
    enabled: bool = True
    scan_level: ScanLevel = ScanLevel.BOTH
    action: FirewallAction = FirewallAction.WARN
    keyword_patterns: list[str] = Field(default_factory=list)
    embedding_threshold: float | None = None
    llm_classification: bool = False
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    description: str = ""


class DURCResult(BaseModel):
    """Result of scanning a single piece of text for a single rule."""

    triggered: bool
    category: DURCCategory
    rule_id: str
    match_type: MatchType
    matched_text: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    action_taken: FirewallAction = FirewallAction.FLAG
    timestamp: datetime = Field(default_factory=datetime.now)


class EthicsDecision(BaseModel):
    """The complete result of scanning a prompt or response through the firewall."""

    decision_id: str = ""
    scan_timestamp: datetime = Field(default_factory=datetime.now)
    scan_level: ScanLevel = ScanLevel.PROMPT
    categories_flagged: list[DURCResult] = Field(default_factory=list)
    overall_action: FirewallAction = FirewallAction.FLAG
    input_hash: str = ""
    text_snippet: str = ""
    provenance_entry_id: str | None = None
    tier_assignment: TierAssignment | None = None
    governance_blocked: bool = False


class ContestRecord(BaseModel):
    """A user-submitted contest against a firewall decision."""

    contest_id: str
    decision_id: str
    user_id: str
    reason: str
    timestamp: datetime = Field(default_factory=datetime.now)
    reviewed: bool = False
    reviewed_at: datetime | None = None
    review_notes: str = ""
    upheld: bool | None = None


class FirewallAuditEntry(BaseModel):
    """An append-only audit entry recording a firewall decision."""

    entry_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    decision_id: str
    category: str
    action_taken: str
    match_type: str
    matched_content: str
    input_hash: str
    user_id: str = ""
    contested: bool = False
    contest_reason: str = ""
    cryptographic_signature: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TierGovernanceAction(StrEnum):
    """Governance action enforced for a given risk tier."""

    STANDARD = "standard"
    HUMAN_CHECKPOINT = "human_checkpoint"
    COOLING_OFF = "cooling_off"


class TierResult(BaseModel):
    """Result of classifying text into a risk tier."""

    assigned_tier: RiskTier
    domain: str = ""
    domain_label: str = ""
    match_type: MatchType | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    governance_action: TierGovernanceAction = TierGovernanceAction.STANDARD
    timestamp: datetime = Field(default_factory=datetime.now)
    cool_off_hours: int = 24
    cool_off_until: datetime | None = None


class TierAssignment(BaseModel):
    """A persistent tier assignment for a research query, with override support."""

    assignment_id: str
    tier: RiskTier
    domain: str = ""
    confidence: float = 0.0
    match_type: MatchType | None = None
    governance_action: TierGovernanceAction = TierGovernanceAction.STANDARD
    auto_classified: bool = True
    override_justification: str = ""
    provenance_entry_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class OverrideRecord(BaseModel):
    """Record of a manual tier override (escalation or downgrade)."""

    override_id: str
    assignment_id: str
    original_tier: RiskTier
    new_tier: RiskTier
    direction: str = ""
    justification: str = ""
    user_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    provenance_entry_id: str | None = None


class DataOrigin(StrEnum):
    """Classification of data provenance origin."""

    PUBLIC = "public"
    LICENSED = "licensed"
    IRB_APPROVED = "irb_approved"
    INDIGENOUS = "indigenous"
    CLINICAL = "clinical"
    PROPRIETARY = "proprietary"


class ConsentRestriction(StrEnum):
    """Usage restrictions attached to a data source."""

    NO_ANALYSIS = "no_analysis"
    NO_SHARING = "no_sharing"
    NO_EXPORT = "no_export"
    ATTRIBUTION_REQUIRED = "attribution_required"
    DERIVED_RESTRICTIONS = "derived_restrictions"
    TIME_LIMITED = "time_limited"
    PURPOSE_LIMITED = "purpose_limited"


class ExportRestriction(StrEnum):
    """Cross-border data transfer restrictions."""

    GDPR = "gdpr"
    HIPAA = "hipaa"
    ITAR = "itar"
    SOVEREIGN_DATA = "sovereign_data"


class CarbonEstimate(BaseModel):
    """Result of estimating carbon cost for a single query."""

    flops: float = 0.0
    kwh: float = 0.0
    co2e_kg: float = 0.0
    equivalence_text: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class CarbonRecord(BaseModel):
    """Record of a carbon-tracked query with budget context."""

    record_id: str
    decision_id: str = ""
    estimate: CarbonEstimate = Field(default_factory=CarbonEstimate)
    monthly_usage_kwh: float = 0.0
    monthly_budget_kwh: float = 0.0
    percentage_used: float = 0.0
    warning_triggered: bool = False
    blocked: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)


class BudgetStatus(BaseModel):
    """Current status of the monthly carbon budget."""

    current_usage_kwh: float = 0.0
    budget_kwh: float = 0.0
    percentage_used: float = 0.0
    warning: bool = False
    blocked: bool = False


class SovereigntyVerdict(BaseModel):
    """Result of checking data sovereignty and consent constraints."""

    verdict_id: str
    data_origin: DataOrigin = DataOrigin.PUBLIC
    consent_restrictions: list[ConsentRestriction] = Field(default_factory=list)
    export_restrictions: list[ExportRestriction] = Field(default_factory=list)
    approved: bool = True
    requires_human_review: bool = False
    restriction_summary: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class CitationSupport(StrEnum):
    """Relationship between a citation and the claim it supports."""

    SUPPORTS = "supports"
    NEUTRAL = "neutral"
    CONTRADICTS = "contradicts"
    UNVERIFIED = "unverified"


class SourceVerificationStatus(StrEnum):
    """Result of verifying that a cited source exists in known literature."""

    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    RETRACTED = "retracted"
    AMBIGUOUS = "ambiguous"


class Citation(BaseModel):
    """A single citation extracted from generated text."""

    raw_text: str = ""
    source_id: str = ""
    doi: str = ""
    pmid: str = ""
    arxiv_id: str = ""
    authors: str = ""
    year: int | None = None
    support_level: CitationSupport = CitationSupport.UNVERIFIED


class Source(BaseModel):
    """A known source from retrieved literature against which citations are verified."""

    source_id: str = ""
    doi: str = ""
    pmid: str = ""
    arxiv_id: str = ""
    title: str = ""
    authors: str = ""
    year: int | None = None
    journal: str = ""
    abstract: str = ""
    retracted: bool = False
    quality: str = "unknown"


class SourceVerification(BaseModel):
    """Result of verifying a citation against known sources."""

    source_id: str
    status: SourceVerificationStatus = SourceVerificationStatus.NOT_FOUND
    detail: str = ""
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)


class UnsupportedClaimFlag(BaseModel):
    """A claim that failed citation enforcement."""

    claim_text: str
    reason: str = ""
    severity: FirewallAction = FirewallAction.FLAG


class GroundingVerdict(BaseModel):
    """Overall result of source grounding checks on generated text."""

    approved: bool = True
    claims_flagged: list[UnsupportedClaimFlag] = Field(default_factory=list)
    citations_verified: list[SourceVerification] = Field(default_factory=list)
    overall_support: CitationSupport = CitationSupport.UNVERIFIED
    timestamp: datetime = Field(default_factory=datetime.now)


class VerifiabilityCategory(StrEnum):
    """Whether a claim is testable with available or foreseeable resources."""

    VERIFIABLE = "verifiable"
    PARTIALLY_VERIFIABLE = "partially_verifiable"
    NON_VERIFIABLE = "non_verifiable"


class VerificationStatus(StrEnum):
    """Lifecycle status of a tracked claim verification."""

    UNCHECKED = "unchecked"
    IN_PROGRESS = "in_progress"
    CONFIRMED = "confirmed"
    REVISED = "revised"
    UNRESOLVED = "unresolved"


class VerificationPath(BaseModel):
    """A suggested experimental or computational verification approach."""

    approach: str
    feasibility: float = Field(default=0.5, ge=0.0, le=1.0)
    resource_estimate: str = ""
    category: VerifiabilityCategory = VerifiabilityCategory.VERIFIABLE


class AsymmetryRecord(BaseModel):
    """Record of a claim's verification asymmetry evaluation."""

    claim_hash: str
    claim_text: str
    category: VerifiabilityCategory
    status: VerificationStatus = VerificationStatus.UNCHECKED
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    asymmetry_gap: float = 0.0
    max_verification_score: float = 0.0
    verification_paths: list[VerificationPath] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    db_id: int | None = None


class VerificationAsymmetryReport(BaseModel):
    """Aggregate report of verification asymmetry across tracked claims."""

    total_claims: int = 0
    n_verifiable: int = 0
    n_partially_verifiable: int = 0
    n_non_verifiable: int = 0
    verification_rate: float = 0.0
    avg_asymmetry_gap: float = 0.0
    max_asymmetry_gap: float = 0.0
    claims_by_category: dict[str, int] = Field(default_factory=dict)


class ConfabulationType(StrEnum):
    """Type of confabulation detected in a claim."""

    CONTRADICTS_CLAIM = "contradicts_claim"
    CONTRADICTS_LITERATURE = "contradicts_literature"
    NO_LITERATURE_SUPPORT = "no_literature_support"
    CONFIDENCE_TOO_LOW = "confidence_too_low"


class ConfabulationFlag(BaseModel):
    """A single claim flagged for potential confabulation."""

    claim_text: str
    flag_type: ConfabulationType = ConfabulationType.NO_LITERATURE_SUPPORT
    severity: float = Field(default=0.0, ge=0.0, le=1.0)
    contradicted_by: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    recommended_action: str = ""


class HallucinationRecord(BaseModel):
    """Aggregated hallucination statistics for a domain/topic."""

    domain: str
    total_claims: int = 0
    n_flags: int = 0
    flag_rate: float = 0.0
    auto_escalated: bool = False
    by_type: dict[str, int] = Field(default_factory=dict)


def _empty_hallucination_record() -> HallucinationRecord:
    return HallucinationRecord(domain="")


class ConfabulationReport(BaseModel):
    """Structured output of a full confabulation detection pass."""

    total_claims: int = 0
    n_flagged: int = 0
    flags: list[ConfabulationFlag] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    boundaries: list[KnowledgeBoundaryFlag] = Field(default_factory=list)
    hallucination_stats: HallucinationRecord = Field(default_factory=_empty_hallucination_record)
    auto_escalated: bool = False
    domain: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
