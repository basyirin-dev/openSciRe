from pydantic import BaseModel, Field


class CitationContext(BaseModel):
    citation_text: str = ""
    reference_id: str = ""
    title: str = ""
    year: int | None = None
    authors: str = ""
    chunk_id: str = ""
    sentence: str = ""
    section: str = ""
    is_retracted: bool = False


class CitationNeighborhood(BaseModel):
    paper_id: str = ""
    title: str = ""
    relationship: str = ""
    distance: int = 1
    year: int | None = None
    influence_score: float = 0.0


class CitationDensity(BaseModel):
    reference_id: str = ""
    citation_count: int = 0
    normalized_citation_count: float = 0.0
    pagerank_score: float = 0.0
    density_label: str = "medium"


class ContradictionSignal(BaseModel):
    reference_id: str = ""
    signal_type: str = ""
    confidence: float = 1.0
    description: str = ""


class TemporalWeight(BaseModel):
    reference_id: str = ""
    year: int | None = None
    weight: float = 0.0
    decay_rate: float = 0.1


class CitationContextReport(BaseModel):
    query: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)
    citations: list[CitationContext] = Field(default_factory=list)
    neighborhood: list[CitationNeighborhood] = Field(default_factory=list)
    density_scores: list[CitationDensity] = Field(default_factory=list)
    contradictions: list[ContradictionSignal] = Field(default_factory=list)
    temporal_weights: list[TemporalWeight] = Field(default_factory=list)
