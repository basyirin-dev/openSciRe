from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class GapType(StrEnum):
    coverage = "coverage"
    methodological_monoculture = "methodological_monoculture"
    geographic = "geographic"
    temporal = "temporal"


class GapSeverity(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class LiteratureGap(BaseModel):
    gap_type: GapType
    severity: GapSeverity
    topic: str
    description: str
    recommendation: str
    affected_count: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


class GapReport(BaseModel):
    topic: str
    total_references: int = 0
    gaps: list[LiteratureGap] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config: dict[str, Any] = Field(default_factory=dict)
