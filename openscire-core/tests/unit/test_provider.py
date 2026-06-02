# SPDX-License-Identifier: Apache-2.0

"""Tests for the Model Provider Interface (Phase 2 / Task 2.1)."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx
from openscire.exceptions import ModelProviderError
from openscire.provider import (
    AnthropicProvider,
    ChatMessage,
    Chunk,
    FinishReason,
    GeminiProvider,
    HealthStatus,
    ImagePart,
    ModelCapabilities,
    ModelCard,
    ModelInfo,
    ModelProvider,
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderMetrics,
    RateLimitConfig,
    TextPart,
)
from pydantic import ValidationError


@pytest.fixture
def config() -> ProviderConfig:
    return ProviderConfig(base_url="http://localhost:11434/v1", default_model="test-model")


@pytest.fixture
def messages() -> list[ChatMessage]:
    return [ChatMessage.system("You are helpful"), ChatMessage.user("Hello")]


class TestRateLimitConfig:
    def test_defaults(self) -> None:
        rl = RateLimitConfig()
        assert rl.requests_per_minute == 60
        assert rl.burst_size == 10
        assert rl.retry_after == 5.0
        assert rl.jitter_factor == 0.1

    def test_validation_positive(self) -> None:
        with pytest.raises(ValidationError):
            RateLimitConfig(requests_per_minute=0)
        with pytest.raises(ValidationError):
            RateLimitConfig(burst_size=0)

    def test_jitter_range(self) -> None:
        with pytest.raises(ValidationError):
            RateLimitConfig(jitter_factor=-0.1)
        with pytest.raises(ValidationError):
            RateLimitConfig(jitter_factor=1.5)


class TestProviderConfig:
    def test_defaults(self) -> None:
        cfg = ProviderConfig()
        assert cfg.base_url == ""
        assert cfg.timeout == 30.0
        assert cfg.max_retries == 3
        assert isinstance(cfg.rate_limit_config, RateLimitConfig)

    def test_rate_limit_inherited(self) -> None:
        cfg = ProviderConfig(rate_limit_config=RateLimitConfig(requests_per_minute=30))
        assert cfg.rate_limit_config.requests_per_minute == 30


class TestFinishReason:
    def test_enum_values(self) -> None:
        assert FinishReason.STOP == "stop"
        assert FinishReason.LENGTH == "length"
        assert FinishReason.TOOL_CALLS == "tool_calls"
        assert FinishReason.CONTENT_FILTER == "content_filter"
        assert FinishReason.ERROR == "error"
        assert FinishReason.NULL == "null"

    def test_from_string(self) -> None:
        assert FinishReason("stop") == FinishReason.STOP
        assert FinishReason("length") == FinishReason.LENGTH


class TestChatMessage:
    def test_system(self) -> None:
        msg = ChatMessage.system("You are a helpful assistant.")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant."
        assert msg.tool_calls is None

    def test_user(self) -> None:
        msg = ChatMessage.user("Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant(self) -> None:
        msg = ChatMessage.assistant("Sure, I can help")
        assert msg.role == "assistant"
        assert msg.content == "Sure, I can help"

    def test_assistant_with_tool_calls(self) -> None:
        tc = [{"id": "call_1", "function": {"name": "get_weather", "arguments": "{}"}}]
        msg = ChatMessage.assistant(tool_calls=tc)
        assert msg.role == "assistant"
        assert msg.tool_calls == tc

    def test_tool(self) -> None:
        msg = ChatMessage.tool('{"temp": 72}', "call_1")
        assert msg.role == "tool"
        assert msg.content == '{"temp": 72}'
        assert msg.tool_call_id == "call_1"

    def test_to_dict_basic(self) -> None:
        msg = ChatMessage.user("Hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "Hello"}

    def test_to_dict_tool(self) -> None:
        msg = ChatMessage.tool("result", "call_1")
        d = msg.to_dict()
        assert d["role"] == "tool"
        assert d["tool_call_id"] == "call_1"
        assert d["content"] == "result"


class TestContentPart:
    def test_text_part(self) -> None:
        tp = TextPart(text="Hello")
        assert tp.type == "text"
        assert tp.text == "Hello"

    def test_image_part(self) -> None:
        ip = ImagePart.from_url("https://example.com/img.png", detail="auto")
        assert ip.type == "image_url"
        assert ip.image_url is not None
        assert ip.image_url["url"] == "https://example.com/img.png"
        assert ip.image_url["detail"] == "auto"

    def test_image_part_minimal(self) -> None:
        ip = ImagePart.from_url("https://example.com/img.png")
        assert ip.image_url is not None
        assert "detail" not in ip.image_url

    def test_chat_message_with_content_parts(self) -> None:
        msg = ChatMessage.user(
            [
                TextPart(text="What's in this image?"),
                ImagePart.from_url("https://example.com/img.png"),
            ]
        )
        assert msg.role == "user"
        d = msg.to_dict()
        assert isinstance(d["content"], list)
        assert len(d["content"]) == 2
        assert d["content"][0]["type"] == "text"
        assert d["content"][0]["text"] == "What's in this image?"
        assert d["content"][1]["type"] == "image_url"
        assert d["content"][1]["image_url"]["url"] == "https://example.com/img.png"

    def test_str_content_unchanged(self) -> None:
        msg = ChatMessage.user("Hello")
        d = msg.to_dict()
        assert d["content"] == "Hello"

    def test_system_with_content_parts(self) -> None:
        msg = ChatMessage.system([TextPart(text="You are a helpful assistant.")])
        assert msg.role == "system"
        assert isinstance(msg.content, list)
        assert msg.content[0].text == "You are a helpful assistant."


class TestChunk:
    def test_basic_fields(self) -> None:
        chunk = Chunk(
            delta_content="Hello",
            finish_reason=FinishReason.STOP,
            usage=ProviderMetrics(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        assert chunk.delta_content == "Hello"
        assert chunk.finish_reason == FinishReason.STOP
        assert chunk.usage is not None
        assert chunk.usage.prompt_tokens == 10

    def test_finish_reason_none(self) -> None:
        chunk = Chunk(delta_content="Hello")
        assert chunk.finish_reason is None

    def test_tool_calls(self) -> None:
        tc = [{"id": "call_1", "function": {"name": "f"}}]
        chunk = Chunk(delta_content="", tool_calls=tc)
        assert chunk.tool_calls == tc

    def test_provider_metrics(self) -> None:
        pm = ProviderMetrics(provider_name="test", latency_ms=100.0)
        chunk = Chunk(delta_content="Hello", provider_metrics=pm)
        assert chunk.provider_metrics is not None
        assert chunk.provider_metrics.latency_ms == 100.0


class TestModelInfo:
    def test_basic(self) -> None:
        info = ModelInfo(id="gpt-4o", provider="openai", context_window=128000)
        assert info.id == "gpt-4o"
        assert info.name == ""
        assert info.capabilities.tool_use is False

    def test_with_capabilities(self) -> None:
        caps = ModelCapabilities(tool_use=True, vision=True)
        info = ModelInfo(id="gpt-4o", capabilities=caps)
        assert info.capabilities.tool_use is True


class TestModelCard:
    def test_empty_defaults(self) -> None:
        card = ModelCard()
        assert card.provider == ""
        assert card.known_biases == []
        assert card.safety_ratings == {}

    def test_partial(self) -> None:
        card = ModelCard(provider="openai", intended_use="Chat", limitations=["May hallucinate"])
        assert card.intended_use == "Chat"
        assert len(card.limitations) == 1


class TestModelProviderABC:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            ModelProvider()

    def test_must_implement_stream_chat_and_list_models(self) -> None:
        class Incomplete(ModelProvider):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_works(self) -> None:
        class Minimal(ModelProvider):
            PROVIDER_NAME = "minimal"

            def _do_stream_chat(
                self,
                messages: list[ChatMessage],
                tools: list[dict[str, Any]] | None = None,
                temperature: float | None = None,
                max_tokens: int | None = None,
                provenance_parent_id: str | None = None,
            ) -> AsyncIterator[Chunk]:
                async def _gen() -> AsyncIterator[Chunk]:
                    yield Chunk(delta_content="hi")

                return _gen()

            async def list_models(self) -> list[ModelInfo]:
                return [ModelInfo(id="test")]

        provider = Minimal()
        assert provider._config is not None
        assert provider.PROVIDER_NAME == "minimal"


class TestBuildMetrics:
    def test_build_metrics(self) -> None:
        class Dummy(ModelProvider):
            PROVIDER_NAME = "dummy"

            def _do_stream_chat(
                self,
                messages: list[ChatMessage],
                tools: list[dict[str, Any]] | None = None,
                temperature: float | None = None,
                max_tokens: int | None = None,
                provenance_parent_id: str | None = None,
            ) -> AsyncIterator[Chunk]:
                async def _gen() -> AsyncIterator[Chunk]:
                    yield Chunk(delta_content="")

                return _gen()

            async def list_models(self) -> list[ModelInfo]:
                return [ModelInfo(id="test")]

        p = Dummy()
        pm = p._build_metrics("test_provider", "test_model", 100.0, 10, 5)
        assert pm.provider_name == "test_provider"
        assert pm.model_name == "test_model"
        assert pm.latency_ms == 100.0
        assert pm.prompt_tokens == 10
        assert pm.completion_tokens == 5
        assert pm.total_tokens == 15


class TestBaseDefaults:
    @pytest.fixture
    def provider(self) -> ModelProvider:
        class Full(ModelProvider):
            PROVIDER_NAME = "full"

            def _do_stream_chat(
                self,
                messages: list[ChatMessage],
                tools: list[dict[str, Any]] | None = None,
                temperature: float | None = None,
                max_tokens: int | None = None,
                provenance_parent_id: str | None = None,
            ) -> AsyncIterator[Chunk]:
                async def _gen() -> AsyncIterator[Chunk]:
                    yield Chunk(delta_content="ok")

                return _gen()

            async def list_models(self) -> list[ModelInfo]:
                return [ModelInfo(id="test")]

        return Full()

    @pytest.mark.asyncio
    async def test_get_token_count(self, provider: ModelProvider) -> None:
        assert await provider.get_token_count("") == 1
        assert await provider.get_token_count("Hello world") == 2
        assert await provider.get_token_count("A" * 100) == 25

    @pytest.mark.asyncio
    async def test_get_context_window_default(self, provider: ModelProvider) -> None:
        assert await provider.get_context_window() == 4096

    @pytest.mark.asyncio
    async def test_get_model_card_default(self, provider: ModelProvider) -> None:
        card = await provider.get_model_card()
        assert card.provider == "full"
        assert card.known_biases == []

    def test_supports_tool_use_default(self, provider: ModelProvider) -> None:
        assert provider.supports_tool_use() is False

    def test_supports_vision_default(self, provider: ModelProvider) -> None:
        assert provider.supports_vision() is False

    def test_supports_streaming_default(self, provider: ModelProvider) -> None:
        assert provider.supports_streaming() is True

    @pytest.mark.asyncio
    async def test_health_ok(self, provider: ModelProvider) -> None:
        status = await provider.health()
        assert status.ok is True
        assert status.latency_ms >= 0
        assert status.error == ""

    @pytest.mark.asyncio
    async def test_health_failure(self, provider: ModelProvider) -> None:
        class FailingProvider(ModelProvider):
            PROVIDER_NAME = "failing"

            def _do_stream_chat(
                self,
                messages: list[ChatMessage],
                tools: list[dict[str, Any]] | None = None,
                temperature: float | None = None,
                max_tokens: int | None = None,
                provenance_parent_id: str | None = None,
            ) -> AsyncIterator[Chunk]:
                async def _gen() -> AsyncIterator[Chunk]:
                    yield Chunk(delta_content="")

                return _gen()

            async def list_models(self) -> list[ModelInfo]:
                raise ConnectionError("Cannot reach provider")

        fail = FailingProvider()
        status = await fail.health()
        assert status.ok is False
        assert "Cannot reach provider" in status.error
        assert status.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_health_measures_latency(self, provider: ModelProvider) -> None:
        status = await provider.health()
        assert status.ok is True
        assert status.latency_ms >= 0


SSE_CHUNK_CONTENT = (
    'data: {"id":"1","object":"chat.completion.chunk",'
    '"choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n'
    'data: {"id":"1","object":"chat.completion.chunk",'
    '"choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}\n'
    'data: {"id":"1","object":"chat.completion.chunk",'
    '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n'
    "data: [DONE]\n"
)

MODELS_JSON = (
    b'{"data": [{"id": "gpt-4o", "object": "model"}, {"id": "gpt-3.5-turbo", "object": "model"}]}'
)


class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_stream_chat_yields_chunks(
        self, config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            route = respx.post("http://localhost:11434/v1/chat/completions").respond(
                200,
                text=SSE_CHUNK_CONTENT,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = OpenAICompatibleProvider(config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            assert route.called
            assert len(chunks) >= 2
            contents = "".join(c.delta_content for c in chunks if c.delta_content)
            assert "Hello" in contents

    @pytest.mark.asyncio
    async def test_stream_chat_metrics(
        self, config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").respond(
                200,
                text=SSE_CHUNK_CONTENT,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = OpenAICompatibleProvider(config)
            last_chunk: Chunk | None = None
            async for chunk in provider.stream_chat(messages):
                last_chunk = chunk
            assert last_chunk is not None
            assert last_chunk.provider_metrics is not None
            assert last_chunk.provider_metrics.provider_name == "openai_compatible"

    def test_parse_non_streaming(self) -> None:
        from openscire.provider.openai_adapter import _parse_sse_chunk

        data = {
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "Hello world"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
        }
        chunk = _parse_sse_chunk(data)
        assert chunk is not None
        assert chunk.delta_content == "Hello world"
        assert chunk.finish_reason == FinishReason.STOP

    @pytest.mark.asyncio
    async def test_http_401_error(
        self, config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").respond(
                401,
                json={"error": {"message": "Invalid API key"}},
            )
            provider = OpenAICompatibleProvider(config)
            with pytest.raises(ModelProviderError) as exc_info:
                async for _ in provider.stream_chat(messages):
                    pass
            assert "Authentication" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_429_error(
        self, config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").respond(
                429,
                json={"error": {"message": "Too many requests"}},
            )
            provider = OpenAICompatibleProvider(config)
            with pytest.raises(ModelProviderError) as exc_info:
                async for _ in provider.stream_chat(messages):
                    pass
            assert "Rate limited" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_502_error(
        self, config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").respond(
                502,
                json={"error": {"message": "Bad gateway"}},
            )
            provider = OpenAICompatibleProvider(config)
            with pytest.raises(ModelProviderError) as exc_info:
                async for _ in provider.stream_chat(messages):
                    pass
            assert "unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_health_ok(self, config: ProviderConfig) -> None:
        async with respx.mock:
            respx.get("http://localhost:11434/v1/models").respond(200, json={"data": []})
            provider = OpenAICompatibleProvider(config)
            status = await provider.health()
            assert status.ok is True
            assert status.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_health_failure(self, config: ProviderConfig) -> None:
        async with respx.mock:
            respx.get("http://localhost:11434/v1/models").mock(
                side_effect=httpx.ConnectError("Connection refused"),
            )
            provider = OpenAICompatibleProvider(config)
            status = await provider.health()
            assert status.ok is False

    @pytest.mark.asyncio
    async def test_list_models(self, config: ProviderConfig) -> None:
        async with respx.mock:
            respx.get("http://localhost:11434/v1/models").respond(200, content=MODELS_JSON)
            provider = OpenAICompatibleProvider(config)
            models = await provider.list_models()
            assert len(models) == 2
            assert models[0].id == "gpt-4o"
            assert models[1].id == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_list_models_fallback(self) -> None:
        cfg = ProviderConfig(default_model="gpt-4")
        provider = OpenAICompatibleProvider(cfg)
        models = await provider.list_models()
        assert len(models) == 1
        assert models[0].id == "gpt-4"

    def test_supports_tool_use(self, config: ProviderConfig) -> None:
        provider = OpenAICompatibleProvider(config)
        assert provider.supports_tool_use() is True

    def test_supports_vision(self, config: ProviderConfig) -> None:
        provider = OpenAICompatibleProvider(config)
        assert provider.supports_vision() is True

    @pytest.mark.asyncio
    async def test_get_context_window(self, config: ProviderConfig) -> None:
        provider = OpenAICompatibleProvider(config)
        assert await provider.get_context_window() == 4096

    @pytest.mark.asyncio
    async def test_get_context_window_gpt4(self) -> None:
        cfg = ProviderConfig(base_url="http://localhost:11434/v1", default_model="gpt-4")
        provider = OpenAICompatibleProvider(cfg)
        assert await provider.get_context_window() == 8192

    @pytest.mark.asyncio
    async def test_get_model_card(self, config: ProviderConfig) -> None:
        provider = OpenAICompatibleProvider(config)
        card = await provider.get_model_card()
        assert card.provider == "openai_compatible"
        assert card.intended_use != ""
        assert len(card.limitations) > 0
        assert card.safety_ratings != {}

    @pytest.mark.asyncio
    async def test_sse_empty_content(
        self, config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        empty_sse = (
            'data: {"id":"1","choices":[{"index":0,"delta":{},'
            '"finish_reason":"stop"}]}\ndata: [DONE]\n'
        )
        async with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").respond(
                200,
                text=empty_sse,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = OpenAICompatibleProvider(config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            assert any(c.finish_reason == FinishReason.STOP for c in chunks if c.finish_reason)

    @pytest.mark.asyncio
    async def test_sse_tool_call_delta(
        self, config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        tool_sse = (
            'data: {"id":"1","choices":[{"index":0,"delta":{"tool_calls":'
            '[{"id":"call_1","function":{"name":"get_weather","arguments":""}}]},'
            '"finish_reason":null}]}\n'
            'data: {"id":"1","choices":[{"index":0,"delta":{"tool_calls":'
            '[{"index":0,"function":{"arguments":"{\\"city\\":"}}]},'
            '"finish_reason":null}]}\n'
            'data: {"id":"1","choices":[{"index":0,"delta":{},'
            '"finish_reason":"tool_calls"}]}\n'
            "data: [DONE]\n"
        )
        async with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").respond(
                200,
                text=tool_sse,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = OpenAICompatibleProvider(config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            tool_chunks = [c for c in chunks if c.tool_calls]
            assert len(tool_chunks) > 0
            assert tool_chunks[0].tool_calls is not None
            assert any(
                c.finish_reason == FinishReason.TOOL_CALLS for c in chunks if c.finish_reason
            )

    @pytest.mark.asyncio
    async def test_no_base_url(self, messages: list[ChatMessage]) -> None:
        cfg = ProviderConfig(default_model="test")
        provider = OpenAICompatibleProvider(cfg)
        with pytest.raises((ModelProviderError, httpx.UnsupportedProtocol, httpx.HTTPError)):
            async for _ in provider.stream_chat(messages):
                pass


class TestTokenCounting:
    @pytest.mark.asyncio
    async def test_tiktoken_used_when_available(self) -> None:
        cfg = ProviderConfig(default_model="gpt-4")
        provider = OpenAICompatibleProvider(cfg)
        count = await provider.get_token_count("Hello, world!")
        assert count > 0

    @pytest.mark.asyncio
    async def test_tiktoken_model_specific(self) -> None:
        cfg = ProviderConfig(default_model="gpt-4o")
        provider = OpenAICompatibleProvider(cfg)
        count = await provider.get_token_count("Hello, world!")
        assert count > 0

    @pytest.mark.asyncio
    async def test_tiktoken_no_model_fallback(self) -> None:
        cfg = ProviderConfig(default_model="")
        provider = OpenAICompatibleProvider(cfg)
        count = await provider.get_token_count("Hello, world!")
        # Uses cl100k_base encoding, should return a reasonable count
        assert count > 0
        assert count < 50

    @pytest.mark.asyncio
    async def test_heuristic_fallback_on_import_error(self) -> None:
        provider = OpenAICompatibleProvider(ProviderConfig(default_model="test"))
        __import__("tiktoken")
        import sys

        saved = sys.modules.pop("tiktoken", None)
        sys.modules["tiktoken"] = None  # type: ignore[assignment]
        try:
            count = await provider.get_token_count("Hello, world!")
            # len("Hello, world!") = 13, 13 // 4 = 3
            assert count == 3
        finally:
            if saved:
                sys.modules["tiktoken"] = saved


class TestHelpers:
    def test_guess_context_window(self) -> None:
        from openscire.provider.openai_adapter import _guess_context_window

        assert _guess_context_window("gpt-4-32k") == 32768
        assert _guess_context_window("gpt-4") == 8192
        assert _guess_context_window("claude-3-opus") == 100000
        assert _guess_context_window("llama-3-70b") == 8192
        assert _guess_context_window("unknown-model") == 4096

    def test_parse_sse_chunk_content(self) -> None:
        from openscire.provider.openai_adapter import _parse_sse_chunk

        data = {
            "choices": [
                {"index": 0, "delta": {"content": "Hello"}, "finish_reason": None},
            ],
        }
        chunk = _parse_sse_chunk(data)
        assert chunk is not None
        assert chunk.delta_content == "Hello"
        assert chunk.finish_reason is None

    def test_parse_sse_chunk_empty(self) -> None:
        from openscire.provider.openai_adapter import _parse_sse_chunk

        assert _parse_sse_chunk({}) is None

    def test_extract_error_json(self) -> None:
        from openscire.provider.openai_adapter import _extract_error

        resp = httpx.Response(401, json={"error": {"message": "Bad key"}})
        assert "Bad key" in _extract_error(resp)

    def test_extract_error_text(self) -> None:
        from openscire.provider.openai_adapter import _extract_error

        resp = httpx.Response(502, text="Service Unavailable")
        assert "Service Unavailable" in _extract_error(resp)

    def test_map_http_401(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.openai_adapter import _map_http_error

        err = _map_http_error(401, "bad key")
        assert isinstance(err, ModelProviderError)
        assert err.error_code == ErrorCode.MODEL_AUTH_FAILURE

    def test_map_http_429(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.openai_adapter import _map_http_error

        err = _map_http_error(429, "too fast")
        assert err.error_code == ErrorCode.MODEL_RATE_LIMIT

    def test_map_http_502(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.openai_adapter import _map_http_error

        err = _map_http_error(502, "bad gateway")
        assert err.error_code == ErrorCode.MODEL_CONNECTION_FAILURE

    def test_map_http_unknown(self) -> None:
        from openscire.provider.openai_adapter import _map_http_error

        err = _map_http_error(418, "I'm a teapot")
        assert "418" in str(err)


ANTHROPO_SSE_TEXT_EVENTS = (
    "event: message_start\n"
    'data: {"type":"message_start","message":{'
    '"id":"msg_01","type":"message","role":"assistant",'
    '"content":[],"model":"claude-sonnet-4-20250514",'
    '"stop_reason":null,"stop_sequence":null,'
    '"usage":{"input_tokens":10,"output_tokens":0}}}\n'
    "\n"
    "event: content_block_start\n"
    'data: {"type":"content_block_start","index":0,'
    '"content_block":{"type":"text","text":""}}\n'
    "\n"
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"text_delta","text":"Hello"}}\n'
    "\n"
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"text_delta","text":" world"}}\n'
    "\n"
    "event: content_block_stop\n"
    'data: {"type":"content_block_stop","index":0}\n'
    "\n"
    "event: message_delta\n"
    'data: {"type":"message_delta",'
    '"delta":{"stop_reason":"end_turn","stop_sequence":null},'
    '"usage":{"output_tokens":3}}\n'
    "\n"
    "event: message_stop\n"
    'data: {"type":"message_stop"}\n'
)

ANTHROPO_SSE_THINKING_EVENTS = (
    "event: message_start\n"
    'data: {"type":"message_start","message":{'
    '"id":"msg_02","type":"message","role":"assistant",'
    '"content":[],"model":"claude-sonnet-4-20250514",'
    '"stop_reason":null,"stop_sequence":null,'
    '"usage":{"input_tokens":10,"output_tokens":0}}}\n'
    "\n"
    "event: content_block_start\n"
    'data: {"type":"content_block_start","index":0,'
    '"content_block":{"type":"thinking","thinking":""}}\n'
    "\n"
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"thinking_delta",'
    '"thinking":"I need to reason..."}}\n'
    "\n"
    "event: content_block_stop\n"
    'data: {"type":"content_block_stop","index":0}\n'
    "\n"
    "event: content_block_start\n"
    'data: {"type":"content_block_start","index":1,'
    '"content_block":{"type":"text","text":""}}\n'
    "\n"
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","index":1,'
    '"delta":{"type":"text_delta","text":"The answer"}}\n'
    "\n"
    "event: content_block_stop\n"
    'data: {"type":"content_block_stop","index":1}\n'
    "\n"
    "event: message_delta\n"
    'data: {"type":"message_delta",'
    '"delta":{"stop_reason":"end_turn","stop_sequence":null},'
    '"usage":{"output_tokens":50}}\n'
    "\n"
    "event: message_stop\n"
    'data: {"type":"message_stop"}\n'
)

ANTHROPO_SSE_TOOL_EVENTS = (
    "event: message_start\n"
    'data: {"type":"message_start","message":{'
    '"id":"msg_03","type":"message","role":"assistant",'
    '"content":[],"model":"claude-sonnet-4-20250514",'
    '"stop_reason":null,"stop_sequence":null,'
    '"usage":{"input_tokens":10,"output_tokens":0}}}\n'
    "\n"
    "event: content_block_start\n"
    'data: {"type":"content_block_start","index":0,'
    '"content_block":{"type":"tool_use","id":"toolu_01",'
    '"name":"get_weather","input":{}}}\n'
    "\n"
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"input_json_delta",'
    '"partial_json":"{\\"location\\": \\""}}\n'
    "\n"
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"input_json_delta",'
    '"partial_json":"San Francisco\\"}"}}\n'
    "\n"
    "event: content_block_stop\n"
    'data: {"type":"content_block_stop","index":0}\n'
    "\n"
    "event: message_delta\n"
    'data: {"type":"message_delta",'
    '"delta":{"stop_reason":"tool_use","stop_sequence":null},'
    '"usage":{"output_tokens":20}}\n'
    "\n"
    "event: message_stop\n"
    'data: {"type":"message_stop"}\n'
)


class TestAnthropicHelpers:
    def test_guess_context_window(self) -> None:
        from openscire.provider.anthropic_adapter import _guess_context_window

        assert _guess_context_window("claude-sonnet-4-20250514") == 200000
        assert _guess_context_window("claude-3-haiku-20240307") == 200000
        assert _guess_context_window("unknown-model") == 4096

    def test_stop_reason_mapping(self) -> None:
        from openscire.provider.anthropic_adapter import _stop_reason_to_finish_reason

        assert _stop_reason_to_finish_reason("end_turn") == FinishReason.STOP
        assert _stop_reason_to_finish_reason("tool_use") == FinishReason.TOOL_CALLS
        assert _stop_reason_to_finish_reason("max_tokens") == FinishReason.LENGTH
        assert _stop_reason_to_finish_reason(None) is None

    def test_extract_error_json(self) -> None:
        from openscire.provider.anthropic_adapter import _extract_error

        resp = httpx.Response(401, json={"error": {"message": "Invalid API key"}})
        assert "Invalid API key" in _extract_error(resp)

    def test_extract_error_text(self) -> None:
        from openscire.provider.anthropic_adapter import _extract_error

        resp = httpx.Response(502, text="Service Unavailable")
        assert "Service Unavailable" in _extract_error(resp)

    def test_map_http_401(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.anthropic_adapter import _map_http_error

        err = _map_http_error(401, "bad key")
        assert isinstance(err, ModelProviderError)
        assert err.error_code == ErrorCode.MODEL_AUTH_FAILURE

    def test_map_http_429(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.anthropic_adapter import _map_http_error

        err = _map_http_error(429, "too fast")
        assert err.error_code == ErrorCode.MODEL_RATE_LIMIT

    def test_map_http_502(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.anthropic_adapter import _map_http_error

        err = _map_http_error(502, "bad gateway")
        assert err.error_code == ErrorCode.MODEL_CONNECTION_FAILURE

    def test_map_http_unknown(self) -> None:
        from openscire.provider.anthropic_adapter import _map_http_error

        err = _map_http_error(418, "I'm a teapot")
        assert "418" in str(err)

    def test_capabilities_for_model(self) -> None:
        provider = AnthropicProvider(
            ProviderConfig(
                base_url="https://api.anthropic.com",
                default_model="claude-sonnet-4-20250514",
                api_key="sk-ant-test",
            ),
        )
        caps = provider.get_capabilities("claude-sonnet-4-20250514")
        assert caps.tool_use is True
        assert caps.vision is True
        assert caps.streaming is True
        assert caps.function_calling is True

    def test_capabilities_haiku_no_vision(self) -> None:
        provider = AnthropicProvider(
            ProviderConfig(
                base_url="https://api.anthropic.com",
                default_model="claude-3-haiku",
                api_key="sk-ant-test",
            ),
        )
        caps = provider.get_capabilities("claude-3-haiku")
        assert caps.vision is False


@pytest.fixture
def anthropic_config() -> ProviderConfig:
    return ProviderConfig(
        base_url="https://api.anthropic.com",
        default_model="claude-sonnet-4-20250514",
        api_key="sk-ant-test",
    )


class TestAnthropicProvider:
    @pytest.mark.asyncio
    async def test_stream_chat_text(
        self, anthropic_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            route = respx.post("https://api.anthropic.com/v1/messages").respond(
                200,
                text=ANTHROPO_SSE_TEXT_EVENTS,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = AnthropicProvider(anthropic_config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            assert route.called
            assert len(chunks) >= 2
            contents = "".join(c.delta_content for c in chunks if c.delta_content)
            assert "Hello world" in contents

    @pytest.mark.asyncio
    async def test_stream_chat_extended_thinking(
        self, anthropic_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            route = respx.post("https://api.anthropic.com/v1/messages").respond(
                200,
                text=ANTHROPO_SSE_THINKING_EVENTS,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = AnthropicProvider(anthropic_config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            assert route.called
            thinking_texts = [c.thinking for c in chunks if c.thinking]
            assert len(thinking_texts) >= 1
            assert "I need to reason" in "".join(thinking_texts)
            contents = "".join(c.delta_content for c in chunks if c.delta_content)
            assert "The answer" in contents

    @pytest.mark.asyncio
    async def test_stream_chat_tool_use(
        self, anthropic_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            route = respx.post("https://api.anthropic.com/v1/messages").respond(
                200,
                text=ANTHROPO_SSE_TOOL_EVENTS,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = AnthropicProvider(anthropic_config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            assert route.called
            assert any(c.finish_reason == FinishReason.TOOL_CALLS for c in chunks)

    @pytest.mark.asyncio
    async def test_stream_chat_metrics(
        self, anthropic_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post("https://api.anthropic.com/v1/messages").respond(
                200,
                text=ANTHROPO_SSE_TEXT_EVENTS,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = AnthropicProvider(anthropic_config)
            last_chunk: Chunk | None = None
            async for chunk in provider.stream_chat(messages):
                last_chunk = chunk
            assert last_chunk is not None
            assert last_chunk.provider_metrics is not None
            assert last_chunk.provider_metrics.provider_name == "anthropic"

    @pytest.mark.asyncio
    async def test_stream_chat_http_error(
        self, anthropic_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post("https://api.anthropic.com/v1/messages").respond(
                401,
                json={"error": {"message": "Invalid API key"}},
            )
            provider = AnthropicProvider(anthropic_config)
            with pytest.raises(ModelProviderError) as exc:
                async for _ in provider.stream_chat(messages):
                    pass
            from openscire.constants import ErrorCode

            assert exc.value.error_code == ErrorCode.MODEL_AUTH_FAILURE
            assert "Invalid API key" in str(exc.value)

    @pytest.mark.asyncio
    async def test_stream_chat_rate_limit(
        self, anthropic_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post("https://api.anthropic.com/v1/messages").respond(
                429,
                json={"error": {"message": "Rate limit exceeded"}},
            )
            provider = AnthropicProvider(anthropic_config)
            with pytest.raises(ModelProviderError) as exc:
                async for _ in provider.stream_chat(messages):
                    pass
            from openscire.constants import ErrorCode

            assert exc.value.error_code == ErrorCode.MODEL_RATE_LIMIT

    @pytest.mark.asyncio
    async def test_health_ok(self, anthropic_config: ProviderConfig) -> None:
        provider = AnthropicProvider(anthropic_config)
        status = await provider.health()
        assert status.ok is True
        assert status.latency_ms > 0

    @pytest.mark.asyncio
    async def test_list_models(self, anthropic_config: ProviderConfig) -> None:
        provider = AnthropicProvider(anthropic_config)
        models = await provider.list_models()
        assert len(models) >= 1
        model_ids = [m.id for m in models]
        assert "claude-sonnet-4-20250514" in model_ids

    @pytest.mark.asyncio
    async def test_list_models_all(self) -> None:
        config = ProviderConfig(
            base_url="https://api.anthropic.com",
            api_key="sk-ant-test",
        )
        provider = AnthropicProvider(config)
        models = await provider.list_models()
        assert len(models) >= 8

    @pytest.mark.asyncio
    async def test_get_token_count(self, anthropic_config: ProviderConfig) -> None:
        provider = AnthropicProvider(anthropic_config)
        count = await provider.get_token_count("Hello world, this is a test message")
        assert count > 0
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_get_context_window_default(self, anthropic_config: ProviderConfig) -> None:
        provider = AnthropicProvider(anthropic_config)
        window = await provider.get_context_window()
        assert window == 200000

    @pytest.mark.asyncio
    async def test_get_context_window_unknown_model(self) -> None:
        config = ProviderConfig(
            base_url="https://api.anthropic.com",
            default_model="unknown-model",
            api_key="sk-ant-test",
        )
        provider = AnthropicProvider(config)
        window = await provider.get_context_window()
        assert window == 4096

    def test_headers(self, anthropic_config: ProviderConfig) -> None:
        provider = AnthropicProvider(anthropic_config)
        headers = provider._headers()
        assert headers["x-api-key"] == "sk-ant-test"
        assert headers["anthropic-version"] == "2023-06-01"
        assert headers["Content-Type"] == "application/json"

    def test_build_payload(
        self, anthropic_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        provider = AnthropicProvider(anthropic_config)
        body = provider._build_payload(messages)
        assert body["model"] == "claude-sonnet-4-20250514"
        assert body["max_tokens"] == 8192
        assert len(body["messages"]) >= 1
        assert body["stream"] is True


GEMINI_SSE_TEXT_EVENTS = (
    'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}],"role":"model"},'
    '"finishReason":null,"safetyRatings":[]}],'
    '"usageMetadata":{"promptTokenCount":5,"candidatesTokenCount":1}}\n'
    "\n"
    'data: {"candidates":[{"content":{"parts":[{"text":" world"}],"role":"model"},'
    '"finishReason":"STOP","safetyRatings":[]}],'
    '"usageMetadata":{"promptTokenCount":5,"candidatesTokenCount":2}}\n'
    "\n"
)

GEMINI_SSE_TOOL_EVENTS = (
    'data: {"candidates":[{"content":{"parts":[{"functionCall":{'
    '"name":"get_weather","args":{"location":"San Francisco"}}}],'
    '"role":"model"},"finishReason":"STOP","safetyRatings":[]}],'
    '"usageMetadata":{"promptTokenCount":5,"candidatesTokenCount":5}}\n'
    "\n"
)

GEMINI_SSE_THINKING_EVENTS = (
    'data: {"candidates":[{"content":{"parts":[{"text":"I need to reason...","thought":true}],'
    '"role":"model"},"finishReason":null,"safetyRatings":[]}]}\n'
    "\n"
    'data: {"candidates":[{"content":{"parts":[{"text":"The answer is 42"}],'
    '"role":"model"},"finishReason":"STOP","safetyRatings":[]}]}\n'
    "\n"
)


class TestGeminiHelpers:
    def test_guess_context_window(self) -> None:
        from openscire.provider.gemini_adapter import _guess_context_window

        assert _guess_context_window("gemini-2.5-pro-001") == 1_048_576
        assert _guess_context_window("gemini-2.5-flash-001") == 1_048_576
        assert _guess_context_window("gemini-2.0-flash") == 1_048_576
        assert _guess_context_window("gemini-1.5-pro-002") == 2_097_152
        assert _guess_context_window("gemini-1.5-flash") == 1_048_576
        assert _guess_context_window("gemini-unknown-model") == 1_048_576
        assert _guess_context_window("unknown-model") == 4096

    def test_finish_reason_mapping(self) -> None:
        from openscire.provider.gemini_adapter import _gemini_finish_reason

        assert _gemini_finish_reason("STOP") == FinishReason.STOP
        assert _gemini_finish_reason("MAX_TOKENS") == FinishReason.LENGTH
        assert _gemini_finish_reason("SAFETY") == FinishReason.CONTENT_FILTER
        assert _gemini_finish_reason("RECITATION") == FinishReason.CONTENT_FILTER
        assert _gemini_finish_reason("MALFORMED_FUNCTION_CALL") == FinishReason.ERROR
        assert _gemini_finish_reason(None) is None

    def test_extract_error_json(self) -> None:
        from openscire.provider.gemini_adapter import _extract_error

        resp = httpx.Response(403, json={"error": {"message": "API key invalid"}})
        assert "API key invalid" in _extract_error(resp)

    def test_extract_error_text(self) -> None:
        from openscire.provider.gemini_adapter import _extract_error

        resp = httpx.Response(502, text="Bad Gateway")
        assert "Bad Gateway" in _extract_error(resp)

    def test_map_http_401(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.gemini_adapter import _map_http_error

        err = _map_http_error(401, "bad key")
        assert isinstance(err, ModelProviderError)
        assert err.error_code == ErrorCode.MODEL_AUTH_FAILURE

    def test_map_http_429(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.gemini_adapter import _map_http_error

        err = _map_http_error(429, "too fast")
        assert err.error_code == ErrorCode.MODEL_RATE_LIMIT

    def test_map_http_502(self) -> None:
        from openscire.constants import ErrorCode
        from openscire.provider.gemini_adapter import _map_http_error

        err = _map_http_error(502, "bad gateway")
        assert err.error_code == ErrorCode.MODEL_CONNECTION_FAILURE

    def test_map_http_unknown(self) -> None:
        from openscire.provider.gemini_adapter import _map_http_error

        err = _map_http_error(418, "teapot")
        assert "418" in str(err)

    def test_convert_parts_text(self) -> None:
        from openscire.provider.gemini_adapter import _convert_parts

        parts = _convert_parts([TextPart(text="hello")])
        assert parts == [{"text": "hello"}]

    def test_convert_parts_image(self) -> None:
        from openscire.provider.gemini_adapter import _convert_parts

        parts = _convert_parts([ImagePart.from_url("data:base64,abc")])
        assert len(parts) == 1
        assert "inlineData" in parts[0]

    def test_convert_parts_empty(self) -> None:
        from openscire.provider.gemini_adapter import _convert_parts

        assert _convert_parts([]) == []

    def test_capabilities_for_model(self) -> None:
        provider = GeminiProvider(
            ProviderConfig(
                base_url="https://generativelanguage.googleapis.com",
                default_model="gemini-2.0-flash",
                api_key="test-key",
            ),
        )
        caps = provider.get_capabilities("gemini-2.0-flash")
        assert caps.tool_use is True
        assert caps.vision is True
        assert caps.streaming is True
        assert caps.function_calling is True

    def test_capabilities_flash_lite_no_vision(self) -> None:
        provider = GeminiProvider(
            ProviderConfig(
                base_url="https://generativelanguage.googleapis.com",
                default_model="gemini-2.0-flash-lite",
                api_key="test-key",
            ),
        )
        caps = provider.get_capabilities("gemini-2.0-flash-lite")
        assert caps.vision is False

    def test_parse_response_text(self) -> None:
        from openscire.provider.gemini_adapter import GeminiProvider

        data = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Hello"}], "role": "model"},
                    "finishReason": "STOP",
                }
            ],
        }
        chunks = GeminiProvider._parse_response(data)
        assert len(chunks) >= 1
        contents = "".join(c.delta_content for c in chunks if c.delta_content)
        assert "Hello" in contents
        assert any(c.finish_reason == FinishReason.STOP for c in chunks if c.finish_reason)

    def test_parse_response_tool(self) -> None:
        from openscire.provider.gemini_adapter import GeminiProvider

        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {"name": "get_weather", "args": {"loc": "SF"}},
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
        }
        chunks = GeminiProvider._parse_response(data)
        assert any(c.tool_calls for c in chunks)

    def test_parse_response_thinking(self) -> None:
        from openscire.provider.gemini_adapter import GeminiProvider

        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "thinking...", "thought": True}],
                        "role": "model",
                    },
                }
            ],
        }
        chunks = GeminiProvider._parse_response(data)
        assert any(c.thinking for c in chunks)


@pytest.fixture
def gemini_config() -> ProviderConfig:
    return ProviderConfig(
        base_url="https://generativelanguage.googleapis.com",
        default_model="gemini-2.0-flash",
        api_key="test-key",
    )


class TestGeminiProvider:
    @pytest.mark.asyncio
    async def test_stream_chat_text(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com"
                "/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse",
            ).respond(
                200,
                text=GEMINI_SSE_TEXT_EVENTS,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = GeminiProvider(gemini_config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            assert route.called
            assert len(chunks) >= 2
            contents = "".join(c.delta_content for c in chunks if c.delta_content)
            assert "Hello world" in contents

    @pytest.mark.asyncio
    async def test_stream_chat_thinking(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com"
                "/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse",
            ).respond(
                200,
                text=GEMINI_SSE_THINKING_EVENTS,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = GeminiProvider(gemini_config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            assert route.called
            thinking_texts = [c.thinking for c in chunks if c.thinking]
            assert len(thinking_texts) >= 1
            assert "I need to reason" in "".join(thinking_texts)

    @pytest.mark.asyncio
    async def test_stream_chat_tool_call(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com"
                "/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse",
            ).respond(
                200,
                text=GEMINI_SSE_TOOL_EVENTS,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = GeminiProvider(gemini_config)
            chunks: list[Chunk] = []
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
            assert route.called
            assert any(c.tool_calls for c in chunks)

    @pytest.mark.asyncio
    async def test_stream_chat_metrics(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com"
                "/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse",
            ).respond(
                200,
                text=GEMINI_SSE_TEXT_EVENTS,
                headers={"Content-Type": "text/event-stream"},
            )
            provider = GeminiProvider(gemini_config)
            last_chunk: Chunk | None = None
            async for chunk in provider.stream_chat(messages):
                last_chunk = chunk
            assert last_chunk is not None
            assert last_chunk.provider_metrics is not None
            assert last_chunk.provider_metrics.provider_name == "gemini"

    @pytest.mark.asyncio
    async def test_stream_chat_http_error(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com"
                "/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse",
            ).respond(
                401,
                json={"error": {"message": "API key invalid"}},
            )
            provider = GeminiProvider(gemini_config)
            with pytest.raises(ModelProviderError) as exc:
                async for _ in provider.stream_chat(messages):
                    pass
            from openscire.constants import ErrorCode

            assert exc.value.error_code == ErrorCode.MODEL_AUTH_FAILURE

    @pytest.mark.asyncio
    async def test_stream_chat_rate_limit(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        async with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com"
                "/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse",
            ).respond(
                429,
                json={"error": {"message": "Rate limited"}},
            )
            provider = GeminiProvider(gemini_config)
            with pytest.raises(ModelProviderError) as exc:
                async for _ in provider.stream_chat(messages):
                    pass
            from openscire.constants import ErrorCode

            assert exc.value.error_code == ErrorCode.MODEL_RATE_LIMIT

    @pytest.mark.asyncio
    async def test_health_ok(self, gemini_config: ProviderConfig) -> None:
        async with respx.mock:
            respx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"pageSize": 1},
            ).respond(
                200,
                json={"models": []},
            )
            provider = GeminiProvider(gemini_config)
            status = await provider.health()
            assert status.ok is True

    @pytest.mark.asyncio
    async def test_health_failure(self, gemini_config: ProviderConfig) -> None:
        async with respx.mock:
            respx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"pageSize": 1},
            ).respond(
                500,
                json={"error": {"message": "Internal error"}},
            )
            provider = GeminiProvider(gemini_config)
            status = await provider.health()
            assert status.ok is False

    @pytest.mark.asyncio
    async def test_list_models(self, gemini_config: ProviderConfig) -> None:
        async with respx.mock:
            respx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"filter": "generateContent"},
            ).respond(
                200,
                json={
                    "models": [
                        {"name": "models/gemini-2.0-flash"},
                        {"name": "models/gemini-2.5-pro"},
                    ],
                },
            )
            provider = GeminiProvider(gemini_config)
            models = await provider.list_models()
            assert len(models) >= 2
            model_ids = [m.id for m in models]
            assert "gemini-2.0-flash" in model_ids

    @pytest.mark.asyncio
    async def test_list_models_fallback(self, gemini_config: ProviderConfig) -> None:
        async with respx.mock:
            respx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"filter": "generateContent"},
            ).respond(500, text="Server Error")
            provider = GeminiProvider(gemini_config)
            models = await provider.list_models()
            assert len(models) >= 1
            assert models[0].provider == "gemini"

    def test_headers(self, gemini_config: ProviderConfig) -> None:
        provider = GeminiProvider(gemini_config)
        headers = provider._headers()
        assert headers["x-goog-api-key"] == "test-key"
        assert headers["Content-Type"] == "application/json"

    def test_build_payload(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        provider = GeminiProvider(gemini_config)
        body = provider._build_payload(messages)
        assert "contents" in body
        assert len(body["contents"]) >= 1
        assert body["contents"][0]["role"] in ("user", "model")

    def test_build_payload_with_tools(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        provider = GeminiProvider(gemini_config)
        tools = [{"function": {"name": "get_weather", "description": "Get weather"}}]
        body = provider._build_payload(messages, tools=tools)
        assert "tools" in body
        assert "functionDeclarations" in body["tools"][0]

    def test_build_payload_with_temperature(
        self, gemini_config: ProviderConfig, messages: list[ChatMessage]
    ) -> None:
        provider = GeminiProvider(gemini_config)
        body = provider._build_payload(messages, temperature=0.7)
        assert body["generationConfig"]["temperature"] == 0.7

    def test_build_payload_with_system_message(self) -> None:
        provider = GeminiProvider(
            ProviderConfig(
                base_url="https://generativelanguage.googleapis.com",
                default_model="gemini-2.0-flash",
                api_key="test-key",
            ),
        )
        msgs = [ChatMessage.system("You are helpful"), ChatMessage.user("Hi")]
        body = provider._build_payload(msgs)
        assert "systemInstruction" in body
        assert body["systemInstruction"]["parts"][0]["text"] == "You are helpful"

    @pytest.mark.asyncio
    async def test_get_token_count(self, gemini_config: ProviderConfig) -> None:
        provider = GeminiProvider(gemini_config)
        count = await provider.get_token_count("Hello world")
        assert count > 0
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_get_context_window(self, gemini_config: ProviderConfig) -> None:
        provider = GeminiProvider(gemini_config)
        window = await provider.get_context_window()
        assert window == 1_048_576

    def test_supports_tool_use(self, gemini_config: ProviderConfig) -> None:
        provider = GeminiProvider(gemini_config)
        assert provider.supports_tool_use() is True

    def test_supports_vision(self, gemini_config: ProviderConfig) -> None:
        provider = GeminiProvider(gemini_config)
        assert provider.supports_vision() is True


class TestHealthStatus:
    def test_ok(self) -> None:
        h = HealthStatus(ok=True, latency_ms=42.0)
        assert h.ok is True
        assert h.latency_ms == 42.0
        assert h.error == ""

    def test_failure(self) -> None:
        h = HealthStatus(ok=False, error="timeout")
        assert h.ok is False
        assert h.error == "timeout"
        assert h.latency_ms == 0.0


class TestDetectFromName:
    def test_no_match_returns_none(self) -> None:
        from openscire.provider.quantization import detect_from_name

        assert detect_from_name("llama-3-70b") is None

    def test_gguf_q4_0(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("llama-2-7b-q4_0")
        assert result is not None
        assert result.format == "gguf"
        assert result.level == "Q4_0"
        assert result.bits == 4.0

    def test_gguf_q4_k_m(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("mistral-7b-q4_k_m")
        assert result is not None
        assert result.format == "gguf"
        assert result.level == "Q4_K_M"
        assert result.bits == 4.5

    def test_gguf_q8_0(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("codellama-34b-q8_0")
        assert result is not None
        assert result.format == "gguf"
        assert result.bits == 8.0

    def test_gguf_q2_k(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q2_k")
        assert result is not None
        assert result.format == "gguf"
        assert result.level == "Q2_K"
        assert result.bits == 2.0

    def test_gguf_q3_k_s(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q3_k_s")
        assert result is not None
        assert result.level == "Q3_K_S"

    def test_gguf_q3_k_m(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q3_k_m")
        assert result is not None
        assert result.level == "Q3_K_M"

    def test_gguf_q3_k_l(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q3_k_l")
        assert result is not None
        assert result.level == "Q3_K_L"

    def test_gguf_q4_k_s(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q4_k_s")
        assert result is not None
        assert result.level == "Q4_K_S"

    def test_gguf_q4_1(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q4_1")
        assert result is not None
        assert result.level == "Q4_1"
        assert result.bits == 4.5

    def test_gguf_q5_k_s(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q5_k_s")
        assert result is not None
        assert result.level == "Q5_K_S"

    def test_gguf_q5_k_m(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q5_k_m")
        assert result is not None
        assert result.level == "Q5_K_M"

    def test_gguf_q5_0(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q5_0")
        assert result is not None
        assert result.level == "Q5_0"

    def test_gguf_q5_1(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q5_1")
        assert result is not None
        assert result.level == "Q5_1"

    def test_gguf_q6_k(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-q6_k")
        assert result is not None
        assert result.level == "Q6_K"
        assert result.bits == 6.0

    def test_gguf_f16(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-f16")
        assert result is not None
        assert result.format == "gguf"
        assert result.level == "F16"
        assert result.bits == 16.0

    def test_gguf_f32(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-f32")
        assert result is not None
        assert result.level == "F32"
        assert result.bits == 32.0

    def test_awq(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("codellama-AWQ")
        assert result is not None
        assert result.format == "awq"
        assert result.bits == 4.0

    def test_w4a16(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-w4a16")
        assert result is not None
        assert result.format == "awq"
        assert result.level == "W4A16"

    def test_gptq(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-gptq")
        assert result is not None
        assert result.format == "gptq"
        assert result.bits == 4.0

    def test_gptq_3bit(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-3bit")
        assert result is not None
        assert result.format == "gptq"
        assert result.level == "GPTQ-3bit"
        assert result.bits == 3.0

    def test_gptq_4bit_catchall(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-4bit-128g")
        assert result is not None
        assert result.format == "gptq"
        assert result.bits == 4.0

    def test_exl2(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-4.0bpw-exl2")
        assert result is not None
        assert result.format == "exl2"
        assert result.level == "EXL2-4.0bpw"
        assert result.bits == 4.0

    def test_exl2_3_5bpw(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-3.5bpw")
        assert result is not None
        assert result.format == "exl2"
        assert result.bits == 3.5

    def test_bitsandbytes_nf4(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-nf4")
        assert result is not None
        assert result.format == "bitsandbytes"
        assert result.level == "NF4"
        assert result.bits == 4.0

    def test_bitsandbytes_fp4(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-fp4")
        assert result is not None
        assert result.format == "bitsandbytes"
        assert result.level == "FP4"

    def test_bitsandbytes_8bit(self) -> None:
        from openscire.provider.quantization import detect_from_name

        result = detect_from_name("model-8bit")
        assert result is not None
        assert result.format == "bitsandbytes"
        assert result.level == "8-bit"
        assert result.bits == 8.0


class TestIsUnquantized:
    def test_none_means_unquantized(self) -> None:
        from openscire.provider.quantization import is_unquantized

        assert is_unquantized(None) is True

    def test_quantized_means_not_unquantized(self) -> None:
        from openscire.provider.quantization import is_unquantized

        assert is_unquantized("Q4_0") is False


class TestDetectFromOllamaDetails:
    def test_with_quantization_level(self) -> None:
        from openscire.provider.quantization import detect_from_ollama_details

        result = detect_from_ollama_details({"quantization_level": "Q4_K_M"})
        assert result is not None
        assert result.format == "gguf"
        assert result.level == "Q4_K_M"
        assert result.bits == 4.5

    def test_without_quantization_level(self) -> None:
        from openscire.provider.quantization import detect_from_ollama_details

        result = detect_from_ollama_details({"foo": "bar"})
        assert result is None

    def test_f16(self) -> None:
        from openscire.provider.quantization import detect_from_ollama_details

        result = detect_from_ollama_details({"quantization_level": "F16"})
        assert result is not None
        assert result.bits == 16.0


class TestEstimateModelMemory:
    def test_7b_fp16_default(self) -> None:
        from openscire.provider.quantization import estimate_model_memory_gb

        memory = estimate_model_memory_gb("llama-2-7b")
        assert memory == pytest.approx(15.4, rel=0.1)

    def test_70b_q4(self) -> None:
        from openscire.provider.quantization import estimate_model_memory_gb

        memory = estimate_model_memory_gb("llama-2-70b", "Q4_0")
        assert memory == pytest.approx(38.5, rel=0.1)

    def test_405b_fp16(self) -> None:
        from openscire.provider.quantization import estimate_model_memory_gb

        memory = estimate_model_memory_gb("llama-3-405b")
        assert memory == pytest.approx(891.0, rel=0.1)

    def test_unknown_model_defaults_to_7b(self) -> None:
        from openscire.provider.quantization import estimate_model_memory_gb

        memory = estimate_model_memory_gb("custom-model-f16", "F16")
        assert memory == pytest.approx(15.4, rel=0.1)


class TestExtractParamCount:
    def test_7b(self) -> None:
        from openscire.provider.quantization import _extract_param_count

        assert _extract_param_count("llama-2-7b") == 7.0

    def test_70b(self) -> None:
        from openscire.provider.quantization import _extract_param_count

        assert _extract_param_count("llama-2-70b") == 70.0

    def test_405b(self) -> None:
        from openscire.provider.quantization import _extract_param_count

        assert _extract_param_count("llama-3-405b") == 405.0

    def test_default(self) -> None:
        from openscire.provider.quantization import _extract_param_count

        assert _extract_param_count("no-param-model") == 7.0


class TestBitsForQuantLevel:
    def test_known_levels(self) -> None:
        from openscire.provider.quantization import _bits_for_quant_level

        assert _bits_for_quant_level("Q4_0") == 4.0
        assert _bits_for_quant_level("Q4_K_M") == 4.5
        assert _bits_for_quant_level("F16") == 16.0
        assert _bits_for_quant_level("Q8_0") == 8.0

    def test_unknown_returns_zero(self) -> None:
        from openscire.provider.quantization import _bits_for_quant_level

        assert _bits_for_quant_level("UNKNOWN") == 0.0


class TestCheckResourceWarning:
    def test_quantized_no_warning(self) -> None:
        from openscire.provider.quantization import check_resource_warning

        result = check_resource_warning("llama-2-7b", "Q4_0")
        assert result is None

    def test_unquantized_may_warn(self, monkeypatch: Any) -> None:
        from openscire.provider.quantization import SystemResources, check_resource_warning

        monkeypatch.setattr(
            "openscire.provider.quantization.get_system_resources",
            lambda: SystemResources(
                total_ram_gb=64.0, available_ram_gb=32.0, vram_gb=None, cpu_count=8
            ),
        )
        result = check_resource_warning("llama-3-405b", None)
        assert result is not None
        assert "may be too large" in result

    def test_f16_warning(self, monkeypatch: Any) -> None:
        from openscire.provider.quantization import SystemResources, check_resource_warning

        monkeypatch.setattr(
            "openscire.provider.quantization.get_system_resources",
            lambda: SystemResources(
                total_ram_gb=64.0, available_ram_gb=32.0, vram_gb=None, cpu_count=8
            ),
        )
        result = check_resource_warning("llama-3-405b", "F16")
        assert result is not None
        assert "quantized" in result


class TestListModelsQuantization:
    @pytest.mark.anyio
    async def test_quantization_field_populated(self, respx_mock: Any) -> None:
        from openscire.provider.openai_adapter import OpenAICompatibleProvider

        route = respx_mock.get("http://test.local/v1/models").respond(
            json={
                "data": [
                    {"id": "llama-2-7b-q4_0"},
                    {"id": "mistral-7b"},
                    {"id": "codellama-AWQ"},
                ]
            }
        )
        provider = OpenAICompatibleProvider(
            ProviderConfig(base_url="http://test.local/v1", default_model="test")
        )
        models = await provider.list_models()
        assert len(models) == 3
        assert models[0].quantization == "Q4_0"
        assert models[1].quantization is None
        assert models[2].quantization == "AWQ"
        assert route.called
