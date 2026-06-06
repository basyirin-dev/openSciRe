import enum

from pydantic import BaseModel, Field

from openscire.references.enforcer.cross_check import CrossCheckResult


class CitationMode(str, enum.Enum):
    STRICT = "strict"
    WARN = "warn"
    AUDIT = "audit"


class CitationSuggestion(BaseModel):
    claim_text: str = ""
    suggested_reference_id: str = ""
    suggested_title: str = ""
    confidence: float = 0.0
    authors: str = ""


class UnsupportedClaim(BaseModel):
    claim_text: str = ""
    sentence_index: int = 0
    reason: str = ""
    suggestions: list[CitationSuggestion] = Field(default_factory=list)


class SourceEnforcementReport(BaseModel):
    mode: CitationMode = CitationMode.AUDIT
    total_sentences: int = 0
    cited_sentences: int = 0
    verified_citations: int = 0
    unverified_citations: int = 0
    unsupported_claims: list[UnsupportedClaim] = Field(default_factory=list)
    suggested_citations: int = 0
    approved: bool = True
    cross_check_results: list[CrossCheckResult] = Field(default_factory=list)
    cross_check_enabled: bool = False
