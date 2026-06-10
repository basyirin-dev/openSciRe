"""Pedagogical report models — structured transparency wrapper."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportSection(str, enum.Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    SELECTION_RATIONALE = "selection_rationale"
    PARAMETER_DOCUMENTATION = "parameter_documentation"
    ALTERNATIVE_INTERPRETATIONS = "alternative_interpretations"
    SELF_IDENTIFIED_LIMITATIONS = "self_identified_limitations"
    UNCERTAINTY_INDICATORS = "uncertainty_indicators"
    PROVENANCE = "provenance"


class SectionContent(BaseModel):
    section: ReportSection
    title: str = ""
    body: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class PedagogicalReport(BaseModel):
    title: str = "Research Analysis Report"
    description: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sections: list[SectionContent] = Field(default_factory=list)
    model_id: str = ""
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    generation_params: dict[str, Any] = Field(default_factory=dict)
    total_gaps: int = 0
    total_unsupported_claims: int = 0
    cross_checks_run: int = 0
    cross_checks_failed: int = 0
