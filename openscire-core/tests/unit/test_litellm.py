# SPDX-License-Identifier: Apache-2.0

"""Tests for LiteLLM adapter (Task 2.10)."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from openscire.constants import ErrorCode
from openscire.exceptions import ModelProviderError
from openscire.provider import (
    ChatMessage,
    Chunk,
    FinishReason,
    LiteLLMProvider,
    LiteLLMRouterConfig,
    LiteLLMRouterProvider,
    ProviderConfig,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_CONFIG = ProviderConfig(default_model=DEFAULT_MODEL)


class MockDelta:
    def __init__(self, content: str = "", tool_calls: list[Any] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or None


class MockChoice:
    def __init__(
        self,
        content: str = "",
        finish_reason: str | None = None,
        tool_calls: list[Any] | None = None,
    ) -> None:
        self.delta = MockDelta(content=content, tool_calls=tool_calls)
        self.finish_reason = finish_reason


class MockUsage:
    def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class MockChunk:
    def __init__(
        self,
        content: str = "",
        finish_reason: str | None = None,
        tool_calls: list[Any] | None = None,
        usage: MockUsage | None = None,
        cost: float = 0.0,
    ) -> None:
        self.choices: list[MockChoice] = [
            MockChoice(content=content, finish_reason=finish_reason, tool_calls=tool_calls)
        ]
        self.usage = usage
        self._hidden_params: dict[str, Any] = {}
        if cost:
            self._hidden_params["response_cost"] = cost


def _make_cost_entry(
    _model_id: str,
    max_tokens: int = 4096,
    input_cost: float = 0.0,
    output_cost: float = 0.0,
) -> dict[str, Any]:
    return {
        "max_tokens": max_tokens,
        "input_cost_per_token": input_cost,
        "output_cost_per_token": output_cost,
        "litellm_provider": "openai",
    }


async def _async_gen(items: list[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# LiteLLMError stubs (for monkeypatching)
# ---------------------------------------------------------------------------


class _MockAuthError(Exception):
    pass


class _MockRateLimitError(Exception):
    pass


class _MockContextWindowError(Exception):
    pass


class _MockAPIConnectionError(Exception):
    pass


class _MockBadRequestError(Exception):
    pass


# ---------------------------------------------------------------------------
# TestLiteLLMProviderInit
# ---------------------------------------------------------------------------


class TestLiteLLMProviderInit:
    def test_requires_default_model(self) -> None:
        with pytest.raises(ValueError, match="default_model"):
            LiteLLMProvider(config=ProviderConfig())

    def test_provider_name(self) -> None:
        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        assert p.PROVIDER_NAME == "litellm"

    def test_init_valid(self) -> None:
        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        assert p._config.default_model == DEFAULT_MODEL

    def test_config_defaults_preserved(self) -> None:
        cfg = ProviderConfig(default_model="gpt-4o-mini", timeout=60.0, max_retries=5)
        p = LiteLLMProvider(config=cfg)
        assert p._config.timeout == 60.0
        assert p._config.max_retries == 5


# ---------------------------------------------------------------------------
# TestLiteLLMStreamChat
# ---------------------------------------------------------------------------


class TestLiteLLMStreamChat:
    @pytest.mark.asyncio
    async def test_basic_text_streaming(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod, "model_cost", {DEFAULT_MODEL: _make_cost_entry(DEFAULT_MODEL)}
        )

        async_mock = AsyncMock(
            return_value=_async_gen([MockChunk(content="hello", finish_reason="stop")])
        )
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        chunks: list[Chunk] = [c async for c in p.stream_chat([ChatMessage.user("hi")])]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert "hello" in texts
        stops = [c.finish_reason for c in chunks if c.finish_reason]
        assert FinishReason.STOP in stops

    @pytest.mark.asyncio
    async def test_streaming_with_tool_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock

        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod, "model_cost", {DEFAULT_MODEL: _make_cost_entry(DEFAULT_MODEL)}
        )

        mock_fn = MagicMock()
        mock_fn.name = "get_weather"
        mock_fn.arguments = "{}"

        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.type = "function"
        mock_tc.function = mock_fn

        async_mock = AsyncMock(
            return_value=_async_gen(
                [
                    MockChunk(
                        content="",
                        finish_reason="tool_calls",
                        tool_calls=[mock_tc],
                    )
                ]
            )
        )
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        chunks: list[Chunk] = [c async for c in p.stream_chat([ChatMessage.user("hi")])]
        tool_calls = [c.tool_calls for c in chunks if c.tool_calls]
        assert len(tool_calls) > 0
        assert tool_calls[0][0]["id"] == "call_123"

    @pytest.mark.asyncio
    async def test_streaming_with_vision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod, "model_cost", {DEFAULT_MODEL: _make_cost_entry(DEFAULT_MODEL)}
        )

        async def _fake_acompletion(
            **kwargs: Any,  # noqa: ANN401
        ) -> AsyncIterator[MockChunk]:
            messages = kwargs.get("messages", [])
            assert len(messages) == 1
            content = messages[0].get("content", "")
            assert isinstance(content, list)
            assert content[0]["type"] == "image_url"
            async for c in _async_gen([MockChunk(content="the image shows", finish_reason="stop")]):
                yield c

        async_mock = AsyncMock(side_effect=_fake_acompletion)
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        from openscire.provider.models import ImagePart

        msg = ChatMessage.user([ImagePart(image_url={"url": "https://example.com/img.png"})])
        chunks: list[Chunk] = [c async for c in p.stream_chat([msg])]
        assert any("image shows" in c.delta_content for c in chunks)

    @pytest.mark.asyncio
    async def test_finish_reason_mapping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod, "model_cost", {DEFAULT_MODEL: _make_cost_entry(DEFAULT_MODEL)}
        )
        async_mock = AsyncMock(
            return_value=_async_gen([MockChunk(content="resp", finish_reason="stop")])
        )
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        chunks: list[Chunk] = [c async for c in p.stream_chat([ChatMessage.user("hi")])]
        stops = [c.finish_reason for c in chunks if c.finish_reason]
        assert FinishReason.STOP in stops

    @pytest.mark.asyncio
    async def test_final_usage_chunk_has_cost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod,
            "model_cost",
            {
                DEFAULT_MODEL: _make_cost_entry(
                    DEFAULT_MODEL, input_cost=0.000001, output_cost=0.000002
                )
            },
        )
        async_mock = AsyncMock(
            return_value=_async_gen(
                [
                    MockChunk(
                        content="hello",
                        finish_reason="stop",
                        usage=MockUsage(prompt_tokens=10, completion_tokens=20),
                        cost=0.00005,
                    ),
                ]
            )
        )
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        chunks: list[Chunk] = [c async for c in p.stream_chat([ChatMessage.user("hi")])]
        metrics = [c.provider_metrics for c in chunks if c.provider_metrics]
        assert len(metrics) > 0
        assert metrics[0].cost >= 0.0
        assert metrics[0].prompt_tokens == 10
        assert metrics[0].completion_tokens == 20
        assert metrics[0].total_tokens == 30

    @pytest.mark.asyncio
    async def test_mid_stream_error_mapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(litellm_mod, "AuthenticationError", _MockAuthError)
        async_mock = AsyncMock(side_effect=_MockAuthError("invalid API key"))
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        with pytest.raises(ModelProviderError) as exc_info:
            async for _ in p.stream_chat([ChatMessage.user("hi")]):
                pass  # pragma: no cover
        assert exc_info.value.error_code == ErrorCode.MODEL_AUTH_FAILURE

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(litellm_mod, "RateLimitError", _MockRateLimitError)
        async_mock = AsyncMock(side_effect=_MockRateLimitError("rate limited"))
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        with pytest.raises(ModelProviderError) as exc_info:
            async for _ in p.stream_chat([ChatMessage.user("hi")]):
                pass  # pragma: no cover
        assert exc_info.value.error_code == ErrorCode.MODEL_RATE_LIMIT

    @pytest.mark.asyncio
    async def test_context_window_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(litellm_mod, "ContextWindowExceededError", _MockContextWindowError)
        async_mock = AsyncMock(side_effect=_MockContextWindowError("context window exceeded"))
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        with pytest.raises(ModelProviderError) as exc_info:
            async for _ in p.stream_chat([ChatMessage.user("hi")]):
                pass  # pragma: no cover
        assert exc_info.value.error_code == ErrorCode.MODEL_UNSUPPORTED_CAPABILITY

    @pytest.mark.asyncio
    async def test_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(litellm_mod, "APIConnectionError", _MockAPIConnectionError)
        async_mock = AsyncMock(side_effect=_MockAPIConnectionError("connection failed"))
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        with pytest.raises(ModelProviderError) as exc_info:
            async for _ in p.stream_chat([ChatMessage.user("hi")]):
                pass  # pragma: no cover
        assert exc_info.value.error_code == ErrorCode.MODEL_CONNECTION_FAILURE


# ---------------------------------------------------------------------------
# TestLiteLLMListModels
# ---------------------------------------------------------------------------


class TestLiteLLMListModels:
    @pytest.mark.asyncio
    async def test_returns_model_from_cost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        model_id = "gpt-4o-mini"
        monkeypatch.setattr(
            litellm_mod,
            "model_cost",
            {
                model_id: _make_cost_entry(
                    model_id, max_tokens=16384, input_cost=0.00015, output_cost=0.0006
                )
            },
        )
        p = LiteLLMProvider(config=ProviderConfig(default_model=model_id))
        models = await p.list_models()
        assert len(models) >= 1
        model = models[0]
        assert model.id == model_id
        assert model.context_window == 16384

    @pytest.mark.asyncio
    async def test_fallback_for_unknown_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(litellm_mod, "model_cost", {})
        p = LiteLLMProvider(config=ProviderConfig(default_model="unknown-model"))
        models = await p.list_models()
        assert len(models) >= 1
        assert models[0].id == "unknown-model"
        assert models[0].context_window == 4096

    @pytest.mark.asyncio
    async def test_pricing_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        model_id = "gpt-4o"
        monkeypatch.setattr(
            litellm_mod,
            "model_cost",
            {model_id: _make_cost_entry(model_id, input_cost=0.0000025, output_cost=0.00001)},
        )
        p = LiteLLMProvider(config=ProviderConfig(default_model=model_id))
        models = await p.list_models()
        m = models[0]
        assert m.pricing_per_1k_input == 0.0025
        assert m.pricing_per_1k_output == 0.01


# ---------------------------------------------------------------------------
# TestLiteLLMCapabilities
# ---------------------------------------------------------------------------


class TestLiteLLMCapabilities:
    def test_gpt4o_has_tool_vision(self) -> None:
        p = LiteLLMProvider(config=ProviderConfig(default_model="gpt-4o"))
        caps = p.get_capabilities("gpt-4o")
        assert caps.tool_use
        assert caps.vision

    def test_claude_has_tool_vision(self) -> None:
        p = LiteLLMProvider(config=ProviderConfig(default_model="claude-3-5-sonnet"))
        caps = p.get_capabilities("claude-3-5-sonnet")
        assert caps.tool_use
        assert caps.vision

    def test_unknown_model_conservative(self) -> None:
        p = LiteLLMProvider(config=ProviderConfig(default_model="weird-model-v1"))
        caps = p.get_capabilities("weird-model-v1")
        assert not caps.tool_use
        assert not caps.vision
        assert caps.streaming


# ---------------------------------------------------------------------------
# TestLiteLLMCost
# ---------------------------------------------------------------------------


class TestLiteLLMCost:
    @pytest.mark.asyncio
    async def test_cost_on_final_chunk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod, "model_cost", {DEFAULT_MODEL: _make_cost_entry(DEFAULT_MODEL)}
        )
        async_mock = AsyncMock(
            return_value=_async_gen(
                [
                    MockChunk(
                        content="hello",
                        finish_reason="stop",
                        usage=MockUsage(prompt_tokens=10, completion_tokens=5),
                        cost=0.00003,
                    ),
                ]
            )
        )
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        chunks: list[Chunk] = [c async for c in p.stream_chat([ChatMessage.user("hi")])]
        metrics = [c.provider_metrics for c in chunks if c.provider_metrics]
        assert len(metrics) >= 1
        assert metrics[-1].provider_name == "litellm"

    @pytest.mark.asyncio
    async def test_zero_cost_for_free_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod, "model_cost", {DEFAULT_MODEL: _make_cost_entry(DEFAULT_MODEL)}
        )
        async_mock = AsyncMock(
            return_value=_async_gen(
                [
                    MockChunk(
                        content="hello",
                        finish_reason="stop",
                        usage=MockUsage(prompt_tokens=5, completion_tokens=5),
                    ),
                ]
            )
        )
        monkeypatch.setattr(litellm_mod, "acompletion", async_mock)

        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        chunks: list[Chunk] = [c async for c in p.stream_chat([ChatMessage.user("hi")])]
        metrics = [c.provider_metrics for c in chunks if c.provider_metrics]
        assert len(metrics) >= 1
        assert metrics[-1].cost >= 0.0


# ---------------------------------------------------------------------------
# TestLiteLLMHealth
# ---------------------------------------------------------------------------


class TestLiteLLMHealth:
    @pytest.mark.asyncio
    async def test_healthy_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod, "model_cost", {DEFAULT_MODEL: _make_cost_entry(DEFAULT_MODEL)}
        )
        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        status = await p.health()
        assert status.ok

    @pytest.mark.asyncio
    async def test_unhealthy_model_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        gpt_mini = _make_cost_entry("gpt-4o-mini")
        monkeypatch.setattr(litellm_mod, "model_cost", {"gpt-4o-mini": gpt_mini})
        p = LiteLLMProvider(config=ProviderConfig(default_model="nonexistent"))
        status = await p.health()
        assert status.ok


# ---------------------------------------------------------------------------
# TestLiteLLMRouterProvider
# ---------------------------------------------------------------------------


class TestLiteLLMRouterProvider:
    def test_init_requires_model_list(self) -> None:
        with pytest.raises(ValueError, match="model_list"):
            LiteLLMRouterProvider(model_list=[])

    @pytest.mark.asyncio
    async def test_stream_chat_delegates_to_router(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(
            litellm_mod, "model_cost", {DEFAULT_MODEL: _make_cost_entry(DEFAULT_MODEL)}
        )

        routed: list[dict[str, Any]] = []

        class MockRouter:
            def __init__(self: "MockRouter", **kwargs: Any) -> None:  # noqa: ANN401
                pass

            async def acompletion(
                self: "MockRouter",
                **kwargs: Any,  # noqa: ANN401
            ) -> AsyncIterator[MockChunk]:
                routed.append(kwargs)
                return _async_gen([MockChunk(content="router response", finish_reason="stop")])

            def get_model_names(self: "MockRouter") -> list[str]:
                return [DEFAULT_MODEL]

        monkeypatch.setattr(litellm_mod, "Router", MockRouter)
        monkeypatch.setattr(litellm_mod, "success_callback", [])

        p = LiteLLMRouterProvider(
            model_list=[
                {
                    "model_name": DEFAULT_MODEL,
                    "litellm_params": {"model": DEFAULT_MODEL},
                }
            ],
            config=_DEFAULT_CONFIG,
        )
        chunks: list[Chunk] = [c async for c in p.stream_chat([ChatMessage.user("hi")])]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert "router response" in texts

    @pytest.mark.asyncio
    async def test_supports_tool_use(self) -> None:
        p = LiteLLMRouterProvider(
            model_list=[
                {
                    "model_name": "gpt-4o",
                    "litellm_params": {"model": "gpt-4o"},
                }
            ],
            config=ProviderConfig(default_model="gpt-4o"),
        )
        assert p.supports_tool_use()

    @pytest.mark.asyncio
    async def test_list_models_aggregates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        model_id = "gpt-4o-mini"
        monkeypatch.setattr(litellm_mod, "model_cost", {model_id: _make_cost_entry(model_id)})

        class MockRouter:
            def __init__(self: "MockRouter", **kwargs: Any) -> None:  # noqa: ANN401
                pass

            async def acompletion(
                self: "MockRouter",
                **_kwargs: Any,  # noqa: ANN401
            ) -> AsyncIterator[MockChunk]:
                return _async_gen([])

            def get_model_names(self: "MockRouter") -> list[str]:
                return [model_id]

        monkeypatch.setattr(litellm_mod, "Router", MockRouter)
        monkeypatch.setattr(litellm_mod, "success_callback", [])

        p = LiteLLMRouterProvider(
            model_list=[
                {
                    "model_name": model_id,
                    "litellm_params": {"model": model_id},
                }
            ],
            config=_DEFAULT_CONFIG,
        )
        models = await p.list_models()
        assert len(models) >= 1
        assert models[0].id == model_id

    @pytest.mark.asyncio
    async def test_router_config_delivered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")

        captured: list[dict[str, Any]] = []

        class MockRouter:
            def __init__(self: "MockRouter", **kwargs: Any) -> None:  # noqa: ANN401
                captured.append(kwargs)

            async def acompletion(
                self: "MockRouter",
                **_kwargs: Any,  # noqa: ANN401
            ) -> AsyncIterator[MockChunk]:
                return _async_gen([])

            def get_model_names(self: "MockRouter") -> list[str]:
                return []

        monkeypatch.setattr(litellm_mod, "Router", MockRouter)
        monkeypatch.setattr(litellm_mod, "success_callback", [])

        rc = LiteLLMRouterConfig(num_retries=5, timeout=60.0)
        _ = LiteLLMRouterProvider(
            model_list=[
                {
                    "model_name": "gpt-4o",
                    "litellm_params": {"model": "gpt-4o"},
                }
            ],
            router_config=rc,
        )
        assert len(captured) >= 1
        assert captured[0].get("num_retries") == 5
        assert captured[0].get("timeout") == 60.0


# ---------------------------------------------------------------------------
# TestLiteLLMRouterConfig
# ---------------------------------------------------------------------------


class TestLiteLLMRouterConfig:
    def test_defaults(self) -> None:
        rc = LiteLLMRouterConfig()
        assert rc.num_retries == 3
        assert rc.timeout == 30.0
        assert rc.routing_strategy == "simple-shuffle"

    def test_custom_config(self) -> None:
        rc = LiteLLMRouterConfig(
            num_retries=5,
            timeout=60.0,
            routing_strategy="cost-based-routing",
            allowed_fails=2,
            cooldown_time=15.0,
            enable_weighted_failover=True,
        )
        assert rc.num_retries == 5
        assert rc.routing_strategy == "cost-based-routing"
        assert rc.enable_weighted_failover is True


# ---------------------------------------------------------------------------
# TestLiteLLMErrorMapping (via concrete subclass)
# ---------------------------------------------------------------------------


class TestLiteLLMErrorMapping:
    def test_bad_request_error_mapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        litellm_mod = pytest.importorskip("litellm")
        monkeypatch.setattr(litellm_mod, "BadRequestError", _MockBadRequestError)
        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        mapped = p._map_litellm_error(_MockBadRequestError("bad request"))
        assert mapped.error_code == ErrorCode.MODEL_UNSUPPORTED_CAPABILITY

    def test_unknown_error_fallback(self) -> None:
        pytest.importorskip("litellm")
        p = LiteLLMProvider(config=_DEFAULT_CONFIG)
        mapped = p._map_litellm_error(ValueError("weird"))
        assert mapped.error_code == ErrorCode.MODEL_CONNECTION_FAILURE
