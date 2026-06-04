# SPDX-License-Identifier: Apache-2.0

"""Data models for citation graph analysis."""

from pydantic import BaseModel, Field


class YearCount(BaseModel):
    year: int
    count: int = 0


class InfluenceResult(BaseModel):
    paper_id: str
    score: float = 0.0
    rank: int = 0


class InfluenceReport(BaseModel):
    results: list[InfluenceResult] = Field(default_factory=list)
    convergence: float = 1e-6
    iterations: int = 0
    damping_factor: float = 0.85


class CitationTimeline(BaseModel):
    paper_id: str = ""
    title: str = ""
    yearly_counts: list[YearCount] = Field(default_factory=list)
    total_citations: int = 0


class DecayResult(BaseModel):
    paper_id: str = ""
    title: str = ""
    is_decayed: bool = False
    decay_score: float = 0.0
    peak_year: int | None = None
    peak_velocity: float = 0.0
    recent_velocity: float = 0.0
    reason: str = ""


class DecayReport(BaseModel):
    results: list[DecayResult] = Field(default_factory=list)
    decayed_papers: list[str] = Field(default_factory=list)
    healthy_papers: list[str] = Field(default_factory=list)
    threshold: float = 0.7


class CitationCluster(BaseModel):
    cluster_id: int
    paper_ids: list[str] = Field(default_factory=list)
    size: int = 0
    cohesion: float = 0.0
    avg_year: float | None = None


class ClusterReport(BaseModel):
    clusters: list[CitationCluster] = Field(default_factory=list)
    method: str = ""
    modularity: float = 0.0


class GraphExport(BaseModel):
    format: str = ""
    data: dict = Field(default_factory=dict)


class CitationGraphReport(BaseModel):
    influence: InfluenceReport | None = None
    timelines: list[CitationTimeline] = Field(default_factory=list)
    decay: DecayReport | None = None
    clusters: ClusterReport | None = None
    node_count: int = 0
    edge_count: int = 0
