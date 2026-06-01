# SPDX-License-Identifier: Apache-2.0

"""Pydantic schemas for serialization metadata and container formats."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

CURRENT_SERIALIZATION_VERSION = "1"


class SerializationEnvelope(BaseModel):
    """Wrapper that carries model data alongside version and metadata for safe deserialization."""

    serialization_version: str = CURRENT_SERIALIZATION_VERSION
    model_name: str
    model_version: str = "0.1.0"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # noqa: UP017
    data: dict[str, object] = Field(default_factory=dict)
