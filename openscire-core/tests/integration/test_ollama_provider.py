# SPDX-License-Identifier: Apache-2.0

"""Integration tests for Ollama / local model connectivity (Task 2.11.4).

Tests two paths:
1. Mock-based (always runs) — verifies the ``select_provider`` → ``LiteLLMProvider``
   → options chain end-to-end by capturing kwargs passed to ``litellm.acompletion``.
2. Real Ollama (conditional on ``OLLAMA_HOST``, default ``localhost:11434``) — end-to-end test
   against a running Ollama instance.
"""

import os
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest

_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost:11434")
from openscire.provider import (
    ChatMessage,
    Chunk,
    LiteLLMProvider,
    ProviderConfig,
    select_provider,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.network,
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _MockChunk:
    """Mimics a LiteLLM model response chunk for streaming."""

    def __init__(self, content: str = "", finish_reason: str | None = None) -> None:
        self.choices = [
            type(
                "_Choice",
                (),
                {
                    "delta": type("_Delta", (), {"content": content, "tool_calls": None})(),
                    "finish_reason": finish_reason,
                },
            )()
        ]
        self.usage = None
        self._hidden_params: dict[str, Any] = {}


async def _async_gen(items: list[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# Mock-based integration tests
# ---------------------------------------------------------------------------


class TestLiteLLMProviderChain:
    """Verifies the full provider chain end-to-end through monkeypatched
    ``litellm.acompletion``.

    Unlike unit tests that mock individual adapters, these tests validate
    the integration between ``select_provider``, ``LiteLLMProvider``, and the
    actual ``litellm`` module (with its internal routing and kwargs construction).
    """

    @pytest.mark.asyncio
    async def test_kwargs_include_model_and_messages(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that ``LiteLLMProvider`` passes the correct ``model`` and
        ``messages`` kwargs to ``litellm.acompletion``."""
        litellm_mod = pytest.importorskip("litellm")

        captured: dict[str, Any] = {}

        async def _fake_acompletion(**kwargs: Any) -> AsyncIterator[Any]:  # noqa: ANN401
            captured.update(kwargs)
            async for item in _async_gen([_MockChunk(content="hello", finish_reason="stop")]):
                yield item

        monkeypatch.setattr(litellm_mod, "acompletion", AsyncMock(side_effect=_fake_acompletion))
        monkeypatch.setattr(
            litellm_mod,
            "model_cost",
            {"ollama/llama3.1": {"max_tokens": 8192, "litellm_provider": "ollama"}},
        )

        provider = select_provider("ollama/llama3.1")
        async for _ in provider.stream_chat([ChatMessage.user("hi")]):
            pass

        assert captured.get("model") == "ollama/llama3.1"
        assert len(captured.get("messages", [])) == 1
        assert captured["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_tools_passed_to_litellm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that tools are included in the kwargs when provided."""
        litellm_mod = pytest.importorskip("litellm")

        captured: dict[str, Any] = {}

        async def _fake_acompletion(**kwargs: Any) -> AsyncIterator[Any]:  # noqa: ANN401
            captured.update(kwargs)
            async for item in _async_gen(
                [_MockChunk(content="result", finish_reason="tool_calls")]
            ):
                yield item

        monkeypatch.setattr(litellm_mod, "acompletion", AsyncMock(side_effect=_fake_acompletion))

        provider = LiteLLMProvider(config=ProviderConfig(default_model="gpt-4o-mini"))
        tools = [{"type": "function", "function": {"name": "test"}}]
        async for _ in provider.stream_chat([ChatMessage.user("hi")], tools=tools):
            pass

        assert "tools" in captured
        assert captured["tools"] == tools

    @pytest.mark.asyncio
    async def test_integration_with_factory_for_unknown_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that the factory creates a working provider for an unknown
        model string (the fallback path to LiteLLMProvider)."""
        litellm_mod = pytest.importorskip("litellm")

        captured: dict[str, Any] = {}

        async def _fake_acompletion(**kwargs: Any) -> AsyncIterator[Any]:  # noqa: ANN401
            captured.update(kwargs)
            async for item in _async_gen([_MockChunk(content="ok", finish_reason="stop")]):
                yield item

        monkeypatch.setattr(litellm_mod, "acompletion", AsyncMock(side_effect=_fake_acompletion))

        provider = select_provider("custom-model-from-hf")
        assert isinstance(provider, LiteLLMProvider)

        chunks: list[Chunk] = [c async for c in provider.stream_chat([ChatMessage.user("test")])]
        assert any("ok" in (c.delta_content or "") for c in chunks)
        assert captured.get("model") == "custom-model-from-hf"

    @pytest.mark.asyncio
    async def test_ollama_model_in_litellm_cost_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify an Ollama model entry in ``model_cost`` surfaces via
        ``list_models``."""
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod,
            "model_cost",
            {
                "ollama/llama3.1": {
                    "max_tokens": 8192,
                    "litellm_provider": "ollama",
                },
            },
        )
        provider = LiteLLMProvider(config=ProviderConfig(default_model="ollama/llama3.1"))
        models = await provider.list_models()
        ids = [m.id for m in models]
        assert "ollama/llama3.1" in ids

    @pytest.mark.asyncio
    async def test_ollama_capabilities_conservative(self) -> None:
        """Ollama models should report streaming capability and conservative
        defaults for tool_use/vision."""
        provider = LiteLLMProvider(config=ProviderConfig(default_model="ollama/llama3.2"))
        caps = provider.get_capabilities("ollama/llama3.2")
        assert caps.streaming
        assert not caps.tool_use
        assert not caps.vision


# ---------------------------------------------------------------------------
# Real Ollama integration test (conditional)
# ---------------------------------------------------------------------------


def _ollama_model_name() -> str | None:
    """Return the first available model name prefixed with ``ollama/``,
    or ``None`` if Ollama is unreachable or has no models."""
    import httpx

    try:
        resp = httpx.get(f"http://{_OLLAMA_HOST}/api/tags", timeout=3.0)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        if models:
            name = models[0]["name"]
            return f"ollama/{name}"
    except Exception:
        pass
    return None


_ollama_model = _ollama_model_name()
ollama_reason = "Ollama not running or has no models"


@pytest.mark.skipif(not _ollama_model, reason=ollama_reason)
class TestRealOllama:
    """End-to-end tests against a running Ollama instance.

    All tests in this class are skipped if Ollama is not reachable
    at ``OLLAMA_HOST`` (default ``localhost:11434``) or has no models pulled.
    """

    @pytest.mark.asyncio
    async def test_basic_chat_streaming(self) -> None:
        """Stream a simple chat response from a real Ollama model."""
        provider = select_provider(_ollama_model)
        chunks: list[Chunk] = []
        async for chunk in provider.stream_chat([ChatMessage.user("Say exactly: ok")]):
            chunks.append(chunk)
        texts = [c.delta_content for c in chunks if c.delta_content]
        full = "".join(texts)
        assert len(full) > 0, "No text content in response"

    @pytest.mark.asyncio
    async def test_list_models(self) -> None:
        """List models from a running Ollama — returns at least one entry
        (either from ``model_cost`` or a fallback placeholder)."""
        provider = select_provider(_ollama_model)
        models = await provider.list_models()
        assert len(models) >= 1

    @pytest.mark.asyncio
    async def test_capabilities_detected(self) -> None:
        """Verify capability detection for real Ollama models."""
        provider = select_provider(_ollama_model)
        caps = provider.get_capabilities(_ollama_model)
        assert caps.streaming
