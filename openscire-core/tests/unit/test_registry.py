# SPDX-License-Identifier: Apache-2.0

"""Tests for the ModelRegistry (Task 2.8)."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from openscire.provider import (
    ChatMessage,
    Chunk,
    ModelCapabilities,
    ModelInfo,
    ModelProvider,
    ModelRegistry,
    ProviderConfig,
    get_global_registry,
)


class _MockProvider(ModelProvider):
    """Minimal provider stub for registry tests."""

    PROVIDER_NAME = "mock"

    def __init__(self, model: str = "mock-model") -> None:
        super().__init__(ProviderConfig(default_model=model))

    async def _do_stream_chat(
        self,
        _messages: list[ChatMessage],
        _tools: list[dict[str, Any]] | None = None,
        _temperature: float | None = None,
        _max_tokens: int | None = None,
        _provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        yield Chunk(delta_content="mock")

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="mock-model", name="mock", provider="mock")]

    def get_capabilities(self, _model_id: str | None = None) -> ModelCapabilities:
        return ModelCapabilities(tool_use=True, vision=True, streaming=True)


class TestModelRegistry:
    """Tests for ModelRegistry."""

    @pytest.fixture
    def registry(self) -> ModelRegistry:
        return ModelRegistry()

    @pytest.mark.asyncio
    async def test_get_with_provider_hit_cache(
        self,
        registry: ModelRegistry,
    ) -> None:
        provider = _MockProvider()
        result = await registry.get("mock", "mock-model", provider)
        assert result is not None
        assert result.id == "mock-model"
        assert result.capabilities.tool_use is True

    @pytest.mark.asyncio
    async def test_get_from_cache_second_call(
        self,
        registry: ModelRegistry,
    ) -> None:
        provider = _MockProvider()
        result1 = await registry.get("mock", "mock-model", provider)
        result2 = await registry.get("mock", "mock-model", provider)
        assert result1 is result2

    @pytest.mark.asyncio
    async def test_get_unknown_model_no_provider(
        self,
        registry: ModelRegistry,
    ) -> None:
        result = await registry.get("unknown", "unknown-model")
        assert result is None

    @pytest.mark.asyncio
    async def test_register_and_get(self, registry: ModelRegistry) -> None:
        info = ModelInfo(id="custom-model", name="Custom", provider="test")
        registry.register("test", "custom-model", info)
        result = await registry.get("test", "custom-model")
        assert result is not None
        assert result.name == "Custom"

    @pytest.mark.asyncio
    async def test_register_many(self, registry: ModelRegistry) -> None:
        models = [
            ModelInfo(id="model-a", name="A", provider="test"),
            ModelInfo(id="model-b", name="B", provider="test"),
        ]
        registry.register_many("test", models)
        result_a = await registry.get("test", "model-a")
        result_b = await registry.get("test", "model-b")
        assert result_a is not None
        assert result_b is not None

    @pytest.mark.asyncio
    async def test_find_by_capability(self, registry: ModelRegistry) -> None:
        registry.register(
            "p1",
            "vision-model",
            ModelInfo(
                id="vision-model",
                provider="p1",
                capabilities=ModelCapabilities(vision=True),
            ),
        )
        registry.register(
            "p2",
            "text-model",
            ModelInfo(
                id="text-model",
                provider="p2",
                capabilities=ModelCapabilities(vision=False),
            ),
        )
        results = registry.find(capability="vision")
        assert len(results) == 1
        assert results[0].id == "vision-model"

    @pytest.mark.asyncio
    async def test_find_by_provider(self, registry: ModelRegistry) -> None:
        registry.register("provider_a", "m1", ModelInfo(id="m1", provider="provider_a"))
        registry.register("provider_b", "m2", ModelInfo(id="m2", provider="provider_b"))
        results = registry.find(provider="provider_a")
        assert len(results) == 1
        assert results[0].id == "m1"

    @pytest.mark.asyncio
    async def test_find_no_match(self, registry: ModelRegistry) -> None:
        results = registry.find(capability="vision")
        assert results == []

    @pytest.mark.asyncio
    async def test_find_multiple_filters(self, registry: ModelRegistry) -> None:
        registry.register(
            "p1",
            "m1",
            ModelInfo(
                id="m1",
                provider="p1",
                capabilities=ModelCapabilities(vision=True),
            ),
        )
        registry.register(
            "p1",
            "m2",
            ModelInfo(
                id="m2",
                provider="p1",
                capabilities=ModelCapabilities(vision=False),
            ),
        )
        results = registry.find(provider="p1", capability="vision")
        assert len(results) == 1
        assert results[0].id == "m1"

    @pytest.mark.asyncio
    async def test_clear_removes_all(self, registry: ModelRegistry) -> None:
        registry.register("p1", "m1", ModelInfo(id="m1", provider="p1"))
        registry.register("p2", "m2", ModelInfo(id="m2", provider="p2"))
        registry.clear()
        result = await registry.get("p1", "m1")
        assert result is None
        result = await registry.get("p2", "m2")
        assert result is None

    @pytest.mark.asyncio
    async def test_duplicate_register_overwrites(self, registry: ModelRegistry) -> None:
        info1 = ModelInfo(id="m1", name="Original", provider="p1")
        info2 = ModelInfo(id="m1", name="Updated", provider="p1")
        registry.register("p1", "m1", info1)
        registry.register("p1", "m1", info2)
        result = await registry.get("p1", "m1")
        assert result is not None
        assert result.name == "Updated"

    @pytest.mark.asyncio
    async def test_get_with_capability_resolution(self, registry: ModelRegistry) -> None:
        provider = _MockProvider()
        registry.register(
            "mock",
            "mock-model",
            ModelInfo(
                id="mock-model",
                provider="mock",
                capabilities=ModelCapabilities(),
            ),
        )
        result = await registry.get("mock", "mock-model", provider)
        assert result is not None
        assert result.capabilities.tool_use is True
        assert result.capabilities.vision is True

    @pytest.mark.asyncio
    async def test_get_without_provider_uses_cached(self, registry: ModelRegistry) -> None:
        registry.register(
            "test",
            "cached-model",
            ModelInfo(
                id="cached-model",
                provider="test",
                capabilities=ModelCapabilities(vision=True),
            ),
        )
        result = await registry.get("test", "cached-model")
        assert result is not None
        assert result.capabilities.vision is True


def test_global_registry_singleton() -> None:
    reg1 = get_global_registry()
    reg2 = get_global_registry()
    assert reg1 is reg2


def test_global_registry_clear() -> None:
    reg = get_global_registry()
    reg.clear()
    assert len(reg._entries) == 0
