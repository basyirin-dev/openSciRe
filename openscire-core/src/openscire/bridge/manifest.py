# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class QueryManifest(BaseModel):
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    bridge_name: str = ""
    endpoint: str = ""
    kwargs: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QueryManifestBuilder:
    def build(
        self,
        bridge_name: str,
        endpoint: str,
        **params: Any,  # noqa: ANN401
    ) -> QueryManifest:
        return QueryManifest(
            query_parameters=params,
            bridge_name=bridge_name,
            endpoint=endpoint,
            kwargs=params,
        )

    @staticmethod
    def to_provenance_entry(manifest: QueryManifest) -> dict[str, Any]:
        return {
            "action_type": "bridge_query",
            "params": manifest.model_dump(),
        }
