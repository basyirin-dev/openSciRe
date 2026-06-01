from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from openscire.provider.base import ModelProvider, ProviderConfig
from openscire.provider.models import ChatMessage, Chunk, ModelInfo
from pydantic import BaseModel

_entry_counter = 0


class _TrackerEntry(BaseModel):
    """Simplified entry captured from mock tracker for assertions."""

    action_type: str
    model_id: str = ""
    params: dict[str, Any] | None = None
    input_hash: str = ""
    output_hash: str = ""
    parent_ids: list[str] | None = None
    action_id: str = ""


class _MockTracker:
    """Records track() calls for inspection."""

    def __init__(self) -> None:
        self.entries: list[_TrackerEntry] = []

    def track(
        self,
        action_type: str,
        model_id: str = "",
        params: dict[str, Any] | None = None,
        input_hash: str = "",
        output_hash: str = "",
        parent_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> _TrackerEntry:
        global _entry_counter  # noqa: PLW0602
        _entry_counter += 1
        entry = _TrackerEntry(
            action_type=action_type,
            model_id=model_id,
            params=params,
            input_hash=input_hash,
            output_hash=output_hash,
            parent_ids=parent_ids,
            action_id=f"entry-{_entry_counter:03d}",
        )
        self.entries.append(entry)
        return entry


class _YieldProvider(ModelProvider):
    """Provider that yields a single chunk."""

    PROVIDER_NAME = "yield"

    def _do_stream_chat(  # noqa: ARG002
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        async def _gen() -> AsyncIterator[Chunk]:
            yield Chunk(delta_content="hello")

        return _gen()

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="yield")]


class _ErrorProvider(ModelProvider):
    """Provider that raises on stream."""

    PROVIDER_NAME = "error"

    def _do_stream_chat(  # noqa: ARG002
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        async def _gen() -> AsyncIterator[Chunk]:
            raise RuntimeError("stream failure")
            yield  # pragma: no cover

        return _gen()

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="error")]


class _BrokenTracker:
    """Tracker that raises on every call."""

    def track(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401, ARG002
        msg = "tracker broken"
        raise RuntimeError(msg)


class TestProviderProvenance:
    """Tests for automatic provenance recording in ``ModelProvider.stream_chat``."""

    @pytest.mark.asyncio
    async def test_records_input_entry(self) -> None:
        tracker = _MockTracker()
        config = ProviderConfig(default_model="test-model", provenance_tracker=tracker)
        provider = _YieldProvider(config)

        chunks = [c async for c in provider.stream_chat([ChatMessage.user("hi")])]

        assert len(chunks) == 1
        assert len(tracker.entries) == 2
        assert tracker.entries[0].action_type == "model_inference"
        assert tracker.entries[0].model_id == "test-model"

    @pytest.mark.asyncio
    async def test_records_output_entry_after_stream(self) -> None:
        tracker = _MockTracker()
        config = ProviderConfig(default_model="test-model", provenance_tracker=tracker)
        provider = _YieldProvider(config)

        chunks = [c async for c in provider.stream_chat([ChatMessage.user("hi")])]

        assert len(chunks) == 1
        # Input entry + output entry (result)
        assert len(tracker.entries) == 2
        assert tracker.entries[0].action_type == "model_inference"
        assert tracker.entries[1].action_type == "model_inference_result"
        assert tracker.entries[1].parent_ids == [tracker.entries[0].action_id]

    @pytest.mark.asyncio
    async def test_records_error_entry_on_failure(self) -> None:
        tracker = _MockTracker()
        config = ProviderConfig(default_model="test-model", provenance_tracker=tracker)
        provider = _ErrorProvider(config)

        with pytest.raises(RuntimeError, match="stream failure"):
            [c async for c in provider.stream_chat([ChatMessage.user("hi")])]

        assert len(tracker.entries) == 2
        assert tracker.entries[0].action_type == "model_inference"
        assert tracker.entries[1].action_type == "model_inference_error"
        assert "stream failure" in str(tracker.entries[1].params or {})

    @pytest.mark.asyncio
    async def test_broken_tracker_does_not_crash_stream(self) -> None:
        tracker = _BrokenTracker()
        config = ProviderConfig(default_model="test-model", provenance_tracker=tracker)
        provider = _YieldProvider(config)

        chunks = [c async for c in provider.stream_chat([ChatMessage.user("hi")])]

        assert len(chunks) == 1
        assert chunks[0].delta_content == "hello"

    @pytest.mark.asyncio
    async def test_no_tracker_no_recording(self) -> None:
        config = ProviderConfig(default_model="test-model")
        provider = _YieldProvider(config)

        chunks = [c async for c in provider.stream_chat([ChatMessage.user("hi")])]

        assert len(chunks) == 1
        # No tracker configured, nothing to check beyond successful streaming

    @pytest.mark.asyncio
    async def test_provenance_parent_id_is_linked(self) -> None:
        tracker = _MockTracker()
        config = ProviderConfig(default_model="test-model", provenance_tracker=tracker)
        provider = _YieldProvider(config)

        parent_id = "parent-123"
        chunks = [
            c
            async for c in provider.stream_chat(
                [ChatMessage.user("hi")],
                provenance_parent_id=parent_id,
            )
        ]

        assert len(chunks) == 1
        assert tracker.entries[0].parent_ids == ["parent-123"]
