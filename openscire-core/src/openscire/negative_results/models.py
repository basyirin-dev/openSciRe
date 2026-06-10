# SPDX-License-Identifier: Apache-2.0

"""Data models for the Negative Result Registry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class NegativeResultOutcome(StrEnum):
    """Classification of what happened when the hypothesis was tested."""

    null = "null"
    contradictory = "contradictory"
    inconclusive = "inconclusive"
    methodological_failure = "methodological_failure"
    partial = "partial"


class NegativeResult(BaseModel):
    """A record of a negative (falsified, contradictory, or inconclusive) result.

    Stored in the RegistryStore and exportable to JSON/CSV/RO-Crate.
    """

    result_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    hypothesis: str = ""
    method_used: str = Field(default="", description="Method/experiment used")
    data_summary: str = Field(default="", description="Brief summary of evidence")
    outcome: NegativeResultOutcome = NegativeResultOutcome.inconclusive
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason_for_failure: str = Field(default="", description="Why the hypothesis failed")
    suggestions: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = Field(default="", description="Agent that registered this")
    ttl_days: int = Field(default=365, gt=0)
    expires_at: datetime | None = None
    provenance_entry_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _parse_json_strings(cls, data: Any) -> Any:  # noqa: ANN401
        """Parse JSON-encoded list fields when loading from SQLite.

        SQLite returns JSON arrays as plain strings (e.g. '["a","b"]'),
        but Pydantic expects Python lists.  This interceptor converts
        them before standard validation runs.
        """
        if not isinstance(data, dict):
            return data
        json_fields = ("suggestions", "source_references", "domain_tags")
        for field in json_fields:
            val = data.get(field)
            if isinstance(val, str):
                try:
                    data[field] = json.loads(val)
                except json.JSONDecodeError:
                    data[field] = []
        return data


class NegativeResultQuery(BaseModel):
    """Search / filter parameters for querying the registry."""

    domain: str | None = None
    topic: str | None = None
    method: str | None = None
    outcome: NegativeResultOutcome | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    created_by: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
