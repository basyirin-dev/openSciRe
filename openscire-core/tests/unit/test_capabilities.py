# SPDX-License-Identifier: Apache-2.0

"""Tests for Runtime Feature Detection (Task 2.8)."""

from __future__ import annotations

import pytest
from openscire.provider import (
    CapabilityProbe,
    ChatMessage,
    ImagePart,
    ModelCapabilities,
    TextPart,
    strip_unsupported,
    tool_call_to_canonical,
    tool_to_provider,
)


class TestCapabilityProbe:
    """Tests for CapabilityProbe heuristic lookup and caching."""

    @pytest.fixture
    def probe(self) -> CapabilityProbe:
        return CapabilityProbe()

    @pytest.mark.asyncio
    async def test_detect_known_openai_model(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("openai_compatible", "gpt-4o")
        assert caps.tool_use is True
        assert caps.vision is True
        assert caps.streaming is True
        assert caps.function_calling is True

    @pytest.mark.asyncio
    async def test_detect_known_anthropic_model(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("anthropic", "claude-sonnet-4")
        assert caps.tool_use is True
        assert caps.vision is True
        assert caps.streaming is True

    @pytest.mark.asyncio
    async def test_detect_haiku_no_vision(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("anthropic", "claude-haiku-3-5")
        assert caps.vision is False

    @pytest.mark.asyncio
    async def test_detect_gemini_flash_lite_no_vision(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("gemini", "gemini-2.0-flash-lite")
        assert caps.vision is False

    @pytest.mark.asyncio
    async def test_detect_gemini_pro_has_vision(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("gemini", "gemini-2.5-pro")
        assert caps.vision is True
        assert caps.tool_use is True

    @pytest.mark.asyncio
    async def test_detect_pattern_match_unknown_gpt4(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("openai_compatible", "gpt-4-unknown-variant")
        assert caps.vision is True
        assert caps.tool_use is True

    @pytest.mark.asyncio
    async def test_detect_pattern_match_llama(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("local", "llama-3-8b")
        assert caps.tool_use is True
        assert caps.vision is False
        assert caps.streaming is True

    @pytest.mark.asyncio
    async def test_detect_unknown_model_fallback(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("unknown_provider", "completely-random-model-v42")
        assert caps.tool_use is False
        assert caps.vision is False
        assert caps.streaming is True

    @pytest.mark.asyncio
    async def test_detect_unknown_model_with_defaults(self, probe: CapabilityProbe) -> None:
        defaults = ModelCapabilities(tool_use=True, vision=True, streaming=True)
        caps = await probe.discover(
            "unknown_provider",
            "random-model",
            provider_defaults=defaults,
        )
        assert caps.tool_use is True
        assert caps.vision is True

    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_instance(self, probe: CapabilityProbe) -> None:
        caps1 = await probe.discover("test", "gpt-4o")
        caps2 = await probe.discover("test", "gpt-4o")
        assert caps1 is caps2

    @pytest.mark.asyncio
    async def test_cache_miss_different_provider(self, probe: CapabilityProbe) -> None:
        caps1 = await probe.discover("provider_a", "gpt-4o")
        caps2 = await probe.discover("provider_b", "gpt-4o")
        assert caps1 == caps2

    @pytest.mark.asyncio
    async def test_cache_invalidate_single_entry(self, probe: CapabilityProbe) -> None:
        await probe.discover("test", "gpt-4o")
        await probe.discover("test", "claude-sonnet-4")
        probe.invalidate(provider_name="test", model_id="gpt-4o")
        caps = await probe.discover("test", "gpt-4o")
        assert caps is not None

    @pytest.mark.asyncio
    async def test_cache_invalidate_provider(self, probe: CapabilityProbe) -> None:
        await probe.discover("provider_a", "gpt-4o")
        await probe.discover("provider_b", "claude-sonnet-4")
        probe.invalidate(provider_name="provider_a")
        assert ("provider_a", "gpt-4o") not in probe._cache
        assert ("provider_b", "claude-sonnet-4") in probe._cache

    @pytest.mark.asyncio
    async def test_cache_invalidate_all(self, probe: CapabilityProbe) -> None:
        await probe.discover("a", "model-1")
        await probe.discover("b", "model-2")
        probe.invalidate()
        assert len(probe._cache) == 0

    @pytest.mark.asyncio
    async def test_cache_eviction_lru(self) -> None:
        probe = CapabilityProbe(max_cache_entries=2)
        await probe.discover("a", "m1")
        await probe.discover("a", "m2")
        await probe.discover("a", "m3")
        assert ("a", "m1") not in probe._cache
        assert ("a", "m2") in probe._cache
        assert ("a", "m3") in probe._cache

    @pytest.mark.asyncio
    async def test_o1_models_no_streaming(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("openai_compatible", "o1")
        assert caps.streaming is False
        caps = await probe.discover("openai_compatible", "o3-mini")
        assert caps.streaming is False

    @pytest.mark.asyncio
    async def test_o1_models_vision_tool_use(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("openai_compatible", "o1")
        assert caps.vision is True
        assert caps.tool_use is True
        caps = await probe.discover("openai_compatible", "o1-mini")
        assert caps.vision is False

    @pytest.mark.asyncio
    async def test_claude_pattern_no_haiku_vision(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("anthropic", "claude-3-opus")
        assert caps.vision is True
        caps = await probe.discover("anthropic", "claude-3-5-sonnet")
        assert caps.vision is True
        caps = await probe.discover("anthropic", "claude-3-haiku")
        assert caps.vision is False

    @pytest.mark.asyncio
    async def test_gemini_patterns(self, probe: CapabilityProbe) -> None:
        caps = await probe.discover("gemini", "gemini-2.5-flash")
        assert caps.vision is True
        caps = await probe.discover("gemini", "gemini-2.0-flash-lite")
        assert caps.vision is False

    def test_runtime_probe_disabled_by_default(self) -> None:
        probe = CapabilityProbe()
        assert probe._enable_runtime_probe is False

    def test_runtime_probe_enabled(self) -> None:
        probe = CapabilityProbe(enable_runtime_probe=True)
        assert probe._enable_runtime_probe is True


class TestStripUnsupported:
    """Tests for graceful degradation of messages and tools."""

    def test_strip_vision_removes_image_part(self) -> None:
        messages = [
            ChatMessage.user("describe this"),
            ChatMessage.user(
                [
                    TextPart(text="what is "),
                    ImagePart.from_url("http://example.com/img.jpg"),
                ]
            ),
        ]
        caps = ModelCapabilities(tool_use=True, vision=False, streaming=True)
        result, tools = strip_unsupported(messages, None, caps)
        assert tools is None
        assert len(result) == 2
        second_content = result[1].content
        assert isinstance(second_content, str)
        assert "[image omitted]" in second_content

    def test_strip_vision_with_only_images(self) -> None:
        messages = [
            ChatMessage.user(
                [
                    ImagePart.from_url("http://example.com/img1.jpg"),
                    ImagePart.from_url("http://example.com/img2.jpg"),
                ]
            ),
        ]
        caps = ModelCapabilities(tool_use=True, vision=False, streaming=True)
        result, _tools = strip_unsupported(messages, None, caps)
        content = result[0].content
        assert isinstance(content, str)
        assert "[2 image(s) omitted]" in content

    def test_strip_vision_with_text_and_image(self) -> None:
        messages = [
            ChatMessage.user(
                [
                    TextPart(text="check this diagram"),
                    ImagePart.from_url("http://example.com/diagram.png"),
                ]
            ),
        ]
        caps = ModelCapabilities(tool_use=True, vision=False, streaming=True)
        result, _tools = strip_unsupported(messages, None, caps)
        content = result[0].content
        assert isinstance(content, str)
        assert "[image omitted]" in content
        assert "check this diagram" in content

    def test_strip_vision_noop_when_supported(self) -> None:
        messages = [
            ChatMessage.user(
                [
                    TextPart(text="hi"),
                    ImagePart.from_url("http://example.com/img.jpg"),
                ]
            ),
        ]
        caps = ModelCapabilities(tool_use=True, vision=True, streaming=True)
        result, _tools = strip_unsupported(messages, None, caps)
        assert result is messages
        assert isinstance(result[0].content, list)
        assert len(result[0].content) == 2

    def test_strip_tools_no_tool_support(self) -> None:
        messages = [ChatMessage.user("hello")]
        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        caps = ModelCapabilities(tool_use=False, vision=True, streaming=True)
        result, result_tools = strip_unsupported(messages, tools, caps)
        assert result_tools is None
        assert len(result) == 2
        assert result[0].role == "system"
        assert "do not have access to tools" in result[0].content.lower()

    def test_strip_tools_noop_when_supported(self) -> None:
        messages = [ChatMessage.user("hello")]
        tools = [{"type": "function", "function": {"name": "test"}}]
        caps = ModelCapabilities(tool_use=True, vision=True, streaming=True)
        result, result_tools = strip_unsupported(messages, tools, caps)
        assert result is messages
        assert result_tools is tools

    def test_strip_tools_noop_with_function_calling(self) -> None:
        messages = [ChatMessage.user("hello")]
        tools = [{"type": "function", "function": {"name": "test"}}]
        caps = ModelCapabilities(tool_use=False, vision=True, streaming=True, function_calling=True)
        result, result_tools = strip_unsupported(messages, tools, caps)
        assert result is messages
        assert result_tools is tools

    def test_strip_all_unsupported(self) -> None:
        messages = [
            ChatMessage.user(
                [
                    TextPart(text="analyze"),
                    ImagePart.from_url("http://example.com/chart.png"),
                ]
            ),
        ]
        tools = [{"type": "function", "function": {"name": "analyze"}}]
        caps = ModelCapabilities(tool_use=False, vision=False, streaming=True)
        result, result_tools = strip_unsupported(messages, tools, caps)
        assert result_tools is None
        assert len(result) == 2
        assert "[image omitted]" in str(result[1].content)

    def test_strip_graceful_degradation_disabled_equivalent(self) -> None:
        messages = [ChatMessage.user("hello")]
        tools = [{"type": "function", "function": {"name": "test"}}]
        caps = ModelCapabilities(tool_use=True, vision=True, streaming=True)
        result, result_tools = strip_unsupported(messages, tools, caps)
        assert result is messages
        assert result_tools is tools


class TestToolFormatConversion:
    """Tests for provider-agnostic tool format conversion."""

    def test_tool_to_provider_openai_passthrough(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]
        result = tool_to_provider(tools, "openai_compatible")
        assert result is tools

    def test_tool_to_provider_anthropic(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {"type": "object"},
                },
            },
        ]
        result = tool_to_provider(tools, "anthropic")
        assert len(result) == 1
        assert result[0]["name"] == "get_weather"
        assert result[0]["description"] == "Get weather"
        assert result[0]["input_schema"] == {"type": "object"}

    def test_tool_to_provider_gemini(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {"type": "object"},
                },
            },
        ]
        result = tool_to_provider(tools, "gemini")
        assert len(result) == 1
        declarations = result[0]["functionDeclarations"]
        assert len(declarations) == 1
        assert declarations[0]["name"] == "get_weather"

    def test_tool_to_provider_unknown_passthrough(self) -> None:
        tools = [{"type": "function", "function": {"name": "test"}}]
        result = tool_to_provider(tools, "unknown_provider")
        assert result is tools

    def test_tool_call_to_canonical_openai_passthrough(self) -> None:
        calls = [
            {"id": "call_1", "type": "function", "function": {"name": "test", "arguments": "{}"}},
        ]
        result = tool_call_to_canonical(calls, "openai_compatible")
        assert result is calls

    def test_tool_call_to_canonical_anthropic(self) -> None:
        calls = [
            {
                "id": "toolu_123",
                "name": "get_weather",
                "input": {"city": "London"},
            },
        ]
        result = tool_call_to_canonical(calls, "anthropic")
        assert len(result) == 1
        assert result[0]["id"] == "toolu_123"
        assert result[0]["function"]["name"] == "get_weather"
        assert result[0]["function"]["arguments"] == '{"city": "London"}'

    def test_tool_call_to_canonical_gemini(self) -> None:
        calls = [
            {
                "name": "get_weather",
                "args": {"city": "Tokyo"},
            },
        ]
        result = tool_call_to_canonical(calls, "gemini")
        assert len(result) == 1
        assert result[0]["function"]["name"] == "get_weather"
        assert result[0]["function"]["arguments"] == '{"city": "Tokyo"}'
        assert result[0]["type"] == "function"

    def test_tool_call_to_canonical_gemini_dict_arguments(self) -> None:
        calls = [
            {
                "name": "search",
                "arguments": {"q": "test"},
            },
        ]
        result = tool_call_to_canonical(calls, "gemini")
        assert result[0]["function"]["arguments"] == '{"q": "test"}'

    def test_tool_call_to_canonical_anthropic_dict_input(self) -> None:
        calls = [
            {
                "id": "toolu_1",
                "name": "fn",
                "input": {"x": 1},
            },
        ]
        result = tool_call_to_canonical(calls, "anthropic")
        assert result[0]["function"]["arguments"] == '{"x": 1}'
