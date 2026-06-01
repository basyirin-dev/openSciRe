# SPDX-License-Identifier: Apache-2.0

"""Tests for the Fallback Cascade (Task 2.6)."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from openscire.constants import ErrorCode
from openscire.exceptions import ModelProviderError
from openscire.provider import (
    CascadeConfig,
    CascadeProvider,
    ChatMessage,
    Chunk,
    FallbackInfo,
    ImagePart,
    ModelInfo,
    ModelProvider,
    ProviderConfig,
    TextPart,
)


class _MockSuccessProvider(ModelProvider):
    """Always succeeds, yields one chunk."""

    PROVIDER_NAME = "mock_success"

    def __init__(self, model: str = "success-model") -> None:
        super().__init__(ProviderConfig(default_model=model))

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        yield Chunk(delta_content="hello from success")

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="success-model", name="success-model", provider="mock_success")]

    def supports_tool_use(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True


class _MockFailProvider(ModelProvider):
    """Fails on stream_chat with a configurable error."""

    PROVIDER_NAME = "mock_fail"

    def __init__(
        self,
        model: str = "fail-model",
        error: Exception | None = None,
        supports_tool: bool = True,
        supports_vision: bool = True,
    ) -> None:
        super().__init__(ProviderConfig(default_model=model))
        self._error = error or ModelProviderError(
            message="mock failure",
            source="test",
            error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
        )
        self._supports_tool = supports_tool
        self._supports_vision = supports_vision

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        if True:
            raise self._error
        yield Chunk()  # pragma: no cover

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="fail-model", name="fail-model", provider="mock_fail")]

    def supports_tool_use(self) -> bool:
        return self._supports_tool

    def supports_vision(self) -> bool:
        return self._supports_vision


@pytest.fixture
def messages() -> list[ChatMessage]:
    return [ChatMessage.user("Hello")]


@pytest.fixture
def cascade_two() -> CascadeProvider:
    success = _MockSuccessProvider()
    fail = _MockFailProvider()
    return CascadeProvider(
        cascade=[("fail", fail), ("success", success)],
        cascade_config=CascadeConfig(user_consent=False),
    )


@pytest.fixture
def cascade_all_fail() -> CascadeProvider:
    fail1 = _MockFailProvider(model="fail-1")
    fail2 = _MockFailProvider(model="fail-2")
    return CascadeProvider(
        cascade=[("first", fail1), ("second", fail2)],
        cascade_config=CascadeConfig(user_consent=False),
    )


class TestCascadeBasic:
    @pytest.mark.anyio
    async def test_first_provider_succeeds(self, messages: list[ChatMessage]) -> None:
        p = CascadeProvider(
            cascade=[("ok", _MockSuccessProvider())],
            cascade_config=CascadeConfig(user_consent=False),
        )
        chunks = [c async for c in p.stream_chat(messages)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]

    @pytest.mark.anyio
    async def test_fallback_on_connection_error(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider(
            error=httpx.ConnectError("connection refused"),
        )
        success = _MockSuccessProvider()
        p = CascadeProvider(
            cascade=[("fail", fail), ("success", success)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        chunks = [c async for c in p.stream_chat(messages)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        fallbacks = [c.fallback_info for c in chunks if c.fallback_info]
        assert texts == ["hello from success"]
        assert len(fallbacks) == 1
        assert fallbacks[0].step_index == 0
        assert "connection refused" in fallbacks[0].error_message

    @pytest.mark.anyio
    async def test_fallback_on_rate_limit(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider(
            error=ModelProviderError(
                message="rate limited",
                source="test",
                error_code=ErrorCode.MODEL_RATE_LIMIT,
            ),
        )
        success = _MockSuccessProvider()
        p = CascadeProvider(
            cascade=[("fail", fail), ("success", success)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        chunks = [c async for c in p.stream_chat(messages)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]

    @pytest.mark.anyio
    async def test_fallback_on_timeout(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider(error=TimeoutError("request timed out"))
        success = _MockSuccessProvider()
        p = CascadeProvider(
            cascade=[("fail", fail), ("success", success)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        chunks = [c async for c in p.stream_chat(messages)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]

    @pytest.mark.anyio
    async def test_fallback_on_5xx(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider(
            error=ModelProviderError(
                message="internal server error",
                source="test",
                error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
            ),
        )
        success = _MockSuccessProvider()
        p = CascadeProvider(
            cascade=[("fail", fail), ("success", success)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        chunks = [c async for c in p.stream_chat(messages)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]


class TestCascadeExhaustion:
    @pytest.mark.anyio
    async def test_all_providers_exhausted(self, messages: list[ChatMessage]) -> None:
        fail1 = _MockFailProvider(model="fail-1")
        fail2 = _MockFailProvider(model="fail-2")
        p = CascadeProvider(
            cascade=[("first", fail1), ("last", fail2)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        with pytest.raises(ModelProviderError) as exc:
            async for _ in p.stream_chat(messages):
                pass
        assert "All cascade providers exhausted" in str(exc.value)
        assert exc.value.error_code == ErrorCode.MODEL_CONNECTION_FAILURE

    @pytest.mark.anyio
    async def test_single_provider_fail_raises(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider()
        p = CascadeProvider(
            cascade=[("only", fail)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        with pytest.raises(ModelProviderError):
            async for _ in p.stream_chat(messages):
                pass


class TestCascadeNonFallbackErrors:
    @pytest.mark.anyio
    async def test_auth_failure_not_fallback_by_default(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider(
            error=ModelProviderError(
                message="unauthorized",
                source="test",
                error_code=ErrorCode.MODEL_AUTH_FAILURE,
            ),
        )
        p = CascadeProvider(
            cascade=[("fail", fail), ("fallback", _MockSuccessProvider())],
            cascade_config=CascadeConfig(user_consent=False),
        )
        with pytest.raises(ModelProviderError) as exc:
            async for _ in p.stream_chat(messages):
                pass
        assert "unauthorized" in str(exc.value)

    @pytest.mark.anyio
    async def test_auth_fallback_when_enabled(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider(
            error=ModelProviderError(
                message="unauthorized",
                source="test",
                error_code=ErrorCode.MODEL_AUTH_FAILURE,
            ),
        )
        p = CascadeProvider(
            cascade=[("fail", fail), ("fallback", _MockSuccessProvider())],
            cascade_config=CascadeConfig(
                user_consent=False,
                include_auth_fallback=True,
            ),
        )
        chunks = [c async for c in p.stream_chat(messages)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]

    @pytest.mark.anyio
    async def test_non_model_error_propagates(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider(error=ValueError("something unexpected"))
        success = _MockSuccessProvider()
        p = CascadeProvider(
            cascade=[("fail", fail), ("success", success)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        with pytest.raises(ValueError, match="something unexpected"):
            async for _ in p.stream_chat(messages):
                pass


class TestCascadeConsent:
    @pytest.mark.anyio
    async def test_consent_callback_allows_fallback(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider()
        success = _MockSuccessProvider()

        async def consent(info: FallbackInfo) -> bool:
            return True

        p = CascadeProvider(
            cascade=[("fail", fail), ("success", success)],
            cascade_config=CascadeConfig(user_consent=True),
            consent_callback=consent,
        )
        chunks = [c async for c in p.stream_chat(messages)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]

    @pytest.mark.anyio
    async def test_consent_callback_denies_fallback(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider()
        success = _MockSuccessProvider()

        async def consent(info: FallbackInfo) -> bool:
            return False

        p = CascadeProvider(
            cascade=[("fail", fail), ("success", success)],
            cascade_config=CascadeConfig(user_consent=True),
            consent_callback=consent,
        )
        with pytest.raises(ModelProviderError) as exc:
            async for _ in p.stream_chat(messages):
                pass
        assert "mock failure" in str(exc.value)

    @pytest.mark.anyio
    async def test_consent_callback_receives_correct_info(
        self, messages: list[ChatMessage]
    ) -> None:
        fail = _MockFailProvider(model="fail-model")
        received: list[FallbackInfo] = []

        async def consent(info: FallbackInfo) -> bool:
            received.append(info)
            return True

        p = CascadeProvider(
            cascade=[("fail", fail), ("ok", _MockSuccessProvider())],
            cascade_config=CascadeConfig(user_consent=True),
            consent_callback=consent,
        )
        async for _ in p.stream_chat(messages):
            pass
        assert len(received) == 1
        assert received[0].step_index == 0
        assert received[0].total_steps == 2
        assert received[0].attempted_provider == "fail"
        assert "mock failure" in received[0].error_message


class TestCascadeGracefulDegradation:
    @pytest.mark.anyio
    async def test_strips_vision_when_fallback_lacks_it(self) -> None:
        vision_msg = ChatMessage(
            role="user",
            content=[
                TextPart(text="describe this"),
                ImagePart(image_url={"url": "https://example.com/img.png"}),
            ],
        )
        fail = _MockFailProvider(
            supports_vision=True,
            error=ModelProviderError(
                message="down",
                source="test",
                error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
            ),
        )
        no_vision = _MockSuccessProvider()
        no_vision.supports_vision = lambda: False  # type: ignore[method-assign]
        p = CascadeProvider(
            cascade=[("vision", fail), ("no-vision", no_vision)],
            cascade_config=CascadeConfig(user_consent=False, graceful_degradation=True),
        )
        chunks = [c async for c in p.stream_chat([vision_msg])]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]

    @pytest.mark.anyio
    async def test_strips_tools_when_fallback_lacks_them(self) -> None:
        fail = _MockFailProvider(
            supports_tool=True,
            error=ModelProviderError(
                message="down",
                source="test",
                error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
            ),
        )
        no_tools = _MockSuccessProvider()
        no_tools.supports_tool_use = lambda: False  # type: ignore[method-assign]
        p = CascadeProvider(
            cascade=[("tools", fail), ("no-tools", no_tools)],
            cascade_config=CascadeConfig(user_consent=False, graceful_degradation=True),
        )
        chunks = [
            c
            async for c in p.stream_chat(
                [ChatMessage.user("hello")],
                tools=[{"type": "function", "function": {"name": "test"}}],
            )
        ]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]

    @pytest.mark.anyio
    async def test_graceful_degradation_disabled_passes_through(self) -> None:
        vision_msg = ChatMessage(
            role="user",
            content=[TextPart(text="hi"), ImagePart(image_url={"url": "https://ex.com/img.png"})],
        )
        no_vision = _MockSuccessProvider()
        no_vision.supports_vision = lambda: False  # type: ignore[method-assign]
        p = CascadeProvider(
            cascade=[("only", no_vision)],
            cascade_config=CascadeConfig(graceful_degradation=False),
        )
        chunks = [c async for c in p.stream_chat([vision_msg])]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["hello from success"]


class TestCascadeModelInfo:
    @pytest.mark.anyio
    async def test_list_models_aggregates(self, cascade_two: CascadeProvider) -> None:
        models = await cascade_two.list_models()
        ids = [m.id for m in models]
        assert ids == ["fail/fail-model", "success/success-model"]
        assert models[0].provider == "cascade:fail"
        assert models[1].provider == "cascade:success"

    @pytest.mark.anyio
    async def test_list_models_skips_failed_providers(self) -> None:
        class _BrokenProvider(ModelProvider):
            PROVIDER_NAME = "broken"

            async def _do_stream_chat(self, *a: Any, **kw: Any) -> AsyncIterator[Chunk]:
                if True:
                    raise ModelProviderError(
                        "broken", source="test", error_code=ErrorCode.MODEL_CONNECTION_FAILURE
                    )
                yield Chunk()  # pragma: no cover

            async def list_models(self) -> list[ModelInfo]:
                raise ModelProviderError(
                    "list fail", source="test", error_code=ErrorCode.MODEL_CONNECTION_FAILURE
                )

        broken = _BrokenProvider()
        ok = _MockSuccessProvider()
        p = CascadeProvider(
            cascade=[("broken", broken), ("ok", ok)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        models = await p.list_models()
        assert len(models) == 1
        assert models[0].id == "ok/success-model"


class TestCascadeCapabilities:
    def test_supports_tool_use_when_any_child_does(self) -> None:
        no_tools = _MockSuccessProvider()
        no_tools.supports_tool_use = lambda: False  # type: ignore[method-assign]
        yes_tools = _MockSuccessProvider()
        p = CascadeProvider(
            cascade=[("a", no_tools), ("b", yes_tools)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        assert p.supports_tool_use() is True

    def test_supports_vision_when_any_child_does(self) -> None:
        no_vision = _MockSuccessProvider()
        no_vision.supports_vision = lambda: False  # type: ignore[method-assign]
        yes_vision = _MockSuccessProvider()
        p = CascadeProvider(
            cascade=[("a", no_vision), ("b", yes_vision)],
            cascade_config=CascadeConfig(user_consent=False),
        )
        assert p.supports_vision() is True

    def test_supports_streaming_when_any_child_does(self) -> None:
        p = CascadeProvider(
            cascade=[("a", _MockSuccessProvider())],
            cascade_config=CascadeConfig(user_consent=False),
        )
        assert p.supports_streaming() is True


class TestCascadeHealth:
    @pytest.mark.anyio
    async def test_healthy_if_any_child_healthy(self, cascade_two: CascadeProvider) -> None:
        status = await cascade_two.health()
        assert status.ok is True

    @pytest.mark.anyio
    async def test_unhealthy_if_all_children_fail(self) -> None:
        class _UnhealthyProvider(ModelProvider):
            PROVIDER_NAME = "unhealthy"

            async def _do_stream_chat(self, *a: Any, **kw: Any) -> AsyncIterator[Chunk]:
                yield Chunk()

            async def list_models(self) -> list[ModelInfo]:
                raise ModelProviderError(
                    "down", source="test", error_code=ErrorCode.MODEL_CONNECTION_FAILURE
                )

        p = CascadeProvider(
            cascade=[("a", _UnhealthyProvider()), ("b", _UnhealthyProvider())],
            cascade_config=CascadeConfig(user_consent=False),
        )
        status = await p.health()
        assert status.ok is False


class TestCascadeValidation:
    def test_empty_cascade_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one provider"):
            CascadeProvider([], cascade_config=CascadeConfig(user_consent=False))


class TestCascadeModelCard:
    @pytest.mark.anyio
    async def test_model_card_returns_cascade_info(self) -> None:
        p = CascadeProvider(
            cascade=[("a", _MockSuccessProvider())],
            cascade_config=CascadeConfig(user_consent=False),
        )
        card = await p.get_model_card()
        assert card.provider == "cascade"
        assert "fallback" in card.intended_use
        assert len(card.limitations) == 3


class TestCascadeContextWindow:
    @pytest.mark.anyio
    async def test_returns_max_of_children(self) -> None:
        small = _MockSuccessProvider()
        small.get_context_window = lambda: (_ async for _ in ()).__anext__().__await__()  # type: ignore[method-assign]

        # Simpler: use a mock
        class _SmallProvider(ModelProvider):
            PROVIDER_NAME = "small"

            async def _do_stream_chat(self, *a: Any, **kw: Any) -> AsyncIterator[Chunk]:
                yield Chunk()

            async def list_models(self) -> list[ModelInfo]:
                return []

            async def get_context_window(self) -> int:
                return 4096

        class _BigProvider(ModelProvider):
            PROVIDER_NAME = "big"

            async def _do_stream_chat(self, *a: Any, **kw: Any) -> AsyncIterator[Chunk]:
                yield Chunk()

            async def list_models(self) -> list[ModelInfo]:
                return []

            async def get_context_window(self) -> int:
                return 128000

        p = CascadeProvider(
            cascade=[("small", _SmallProvider()), ("big", _BigProvider())],
            cascade_config=CascadeConfig(user_consent=False),
        )
        window = await p.get_context_window()
        assert window == 128000


class TestCascadeTokenCount:
    @pytest.mark.anyio
    async def test_delegates_to_first_provider(self) -> None:
        p = CascadeProvider(
            cascade=[("a", _MockSuccessProvider())],
            cascade_config=CascadeConfig(user_consent=False),
        )
        count = await p.get_token_count("hello world")
        assert count == max(1, len("hello world") // 4)


class TestCascadeFallbackInfo:
    @pytest.mark.anyio
    async def test_fallback_info_yielded_in_chunks(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider(
            error=ModelProviderError(
                message="provider unavailable",
                source="test",
                error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
            ),
        )
        p = CascadeProvider(
            cascade=[("fail", fail), ("ok", _MockSuccessProvider())],
            cascade_config=CascadeConfig(user_consent=False),
        )
        chunks: list[Chunk] = [c async for c in p.stream_chat(messages)]
        fallback_chunks = [c for c in chunks if c.fallback_info is not None]
        assert len(fallback_chunks) == 1
        info = fallback_chunks[0].fallback_info
        assert info is not None
        assert info.step_index == 0
        assert info.total_steps == 2
        assert info.attempted_provider == "fail"
        assert info.error_code == "MODEL_CONNECTION_FAILURE"


class TestCascadeProvenanceLogging:
    @pytest.mark.anyio
    async def test_logs_fallback_to_provenance(self, messages: list[ChatMessage]) -> None:
        fail = _MockFailProvider()
        success = _MockSuccessProvider()
        logged: list[dict[str, Any]] = []

        class _MockTracker:
            def track(
                self,
                action_type: str,
                model_id: str,
                params: dict[str, Any] | None = None,
                **kwargs: Any,
            ) -> None:
                logged.append(
                    {
                        "action_type": action_type,
                        "model_id": model_id,
                        "params": params,
                    }
                )

        p = CascadeProvider(
            cascade=[("fail", fail), ("success", success)],
            cascade_config=CascadeConfig(
                user_consent=False,
                log_to_provenance=True,
            ),
            provenance_tracker=_MockTracker(),
        )
        async for _ in p.stream_chat(messages):
            pass
        assert len(logged) == 1
        assert logged[0]["action_type"] == "model_fallback"
        assert logged[0]["model_id"] == "fail-model"
        assert logged[0]["params"]["step_index"] == 0
