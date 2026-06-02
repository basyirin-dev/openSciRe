"""Integration test: provenance recording through ModelProvider stream_chat.

Verifies that a configured ProvenanceTracker records entries when
``stream_chat`` is called, that parent IDs link correctly, and that
exported provenance includes provider inference events.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from openscire.provenance import ProvenanceExporter, ProvenanceTracker
from openscire.provider import (
    ChatMessage,
    Chunk,
    ModelInfo,
    ModelProvider,
    ProviderConfig,
)

from tests.conftest import reset_provenance  # noqa: F401


class _MinimalProvider(ModelProvider):
    """Minimal provider that yields a single chunk."""

    PROVIDER_NAME = "minimal"

    def _do_stream_chat(  # noqa: ARG002
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, object]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        async def _gen() -> AsyncIterator[Chunk]:
            yield Chunk(delta_content="hello from provenance integration")

        return _gen()

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="minimal")]


@pytest.mark.usefixtures("reset_provenance")
class TestProvenanceThroughProvider:
    """Full-cycle test: provider call -> provenance entry -> export."""

    @pytest.mark.asyncio
    async def test_provider_records_provenance(self) -> None:
        tracker = ProvenanceTracker.get_tracker(
            "test-provider",
            storage_backend="in_memory",
        )
        config = ProviderConfig(
            default_model="test-model",
            provenance_tracker=tracker,
        )
        provider = _MinimalProvider(config)

        chunks = [c async for c in provider.stream_chat([ChatMessage.user("hi")])]

        assert len(chunks) == 1
        assert chunks[0].delta_content == "hello from provenance integration"
        assert len(tracker.graph) == 2

    @pytest.mark.asyncio
    async def test_provenance_parent_linking(self) -> None:
        tracker = ProvenanceTracker.get_tracker(
            "test-linking",
            storage_backend="in_memory",
        )
        config = ProviderConfig(
            default_model="test-model",
            provenance_tracker=tracker,
        )
        provider = _MinimalProvider(config)

        parent_id = "external-parent-42"
        chunks = [
            c
            async for c in provider.stream_chat(
                [ChatMessage.user("link me")],
                provenance_parent_id=parent_id,
            )
        ]

        assert len(chunks) == 1
        entries = list(tracker.storage.list())
        input_entry = next(e for e in entries if e.action_type == "model_inference")
        assert parent_id in input_entry.parent_ids

    @pytest.mark.asyncio
    async def test_provenance_export_includes_inference(self) -> None:
        tracker = ProvenanceTracker.get_tracker(
            "test-export",
            storage_backend="in_memory",
        )
        config = ProviderConfig(
            default_model="export-model",
            provenance_tracker=tracker,
        )
        provider = _MinimalProvider(config)

        [c async for c in provider.stream_chat([ChatMessage.user("export test")])]

        entries = list(tracker.storage.list())
        json_output = ProvenanceExporter.to_json(entries)
        parsed = json.loads(json_output)
        action_types = {e["action_type"] for e in parsed["provenance"]}
        assert "model_inference" in action_types
        assert "model_inference_result" in action_types
