# SPDX-License-Identifier: Apache-2.0

"""Runtime feature detection for LLM models.

Provides capability probing, graceful degradation, and provider-agnostic
tool format conversion.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Any

from openscire.provider.models import (
    ChatMessage,
    ImagePart,
    ModelCapabilities,
)

_SUPPORTED_MODELS: dict[str, ModelCapabilities] = {
    # OpenAI
    "gpt-4o": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "gpt-4o-mini": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "gpt-4-turbo": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "gpt-4": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=True,
        function_calling=True,
    ),
    "gpt-4-32k": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=True,
        function_calling=True,
    ),
    "gpt-3.5-turbo": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=True,
        function_calling=True,
    ),
    "gpt-3.5-turbo-16k": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=True,
        function_calling=True,
    ),
    "o1": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=False,
        function_calling=True,
    ),
    "o1-mini": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=False,
        function_calling=True,
    ),
    "o3": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=False,
        function_calling=True,
    ),
    "o3-mini": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=False,
        function_calling=True,
    ),
    "o4-mini": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=False,
        function_calling=True,
    ),
    # Anthropic
    "claude-sonnet-4": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "claude-opus-4": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "claude-haiku-3-5": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=True,
        function_calling=True,
    ),
    "claude-3-5-sonnet": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "claude-3-5-haiku": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=True,
        function_calling=True,
    ),
    "claude-3-opus": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "claude-3-sonnet": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "claude-3-haiku": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=True,
        function_calling=True,
    ),
    # Gemini
    "gemini-2.5-pro": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "gemini-2.5-flash": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "gemini-2.0-flash": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "gemini-2.0-flash-lite": ModelCapabilities(
        tool_use=True,
        vision=False,
        streaming=True,
        function_calling=True,
    ),
    "gemini-1.5-pro": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
    "gemini-1.5-flash": ModelCapabilities(
        tool_use=True,
        vision=True,
        streaming=True,
        function_calling=True,
    ),
}

_PATTERNS: list[tuple[re.Pattern[str], ModelCapabilities]] = [
    (
        re.compile(r"claude-(?!.*haiku)"),
        ModelCapabilities(
            tool_use=True,
            vision=True,
            streaming=True,
            function_calling=True,
        ),
    ),
    (
        re.compile(r"claude.*haiku"),
        ModelCapabilities(
            tool_use=True,
            vision=False,
            streaming=True,
            function_calling=True,
        ),
    ),
    (
        re.compile(r"gpt-4"),
        ModelCapabilities(
            tool_use=True,
            vision=True,
            streaming=True,
            function_calling=True,
        ),
    ),
    (
        re.compile(r"gpt-3\.5"),
        ModelCapabilities(
            tool_use=True,
            vision=False,
            streaming=True,
            function_calling=True,
        ),
    ),
    (
        re.compile(r"gemini.*flash-lite"),
        ModelCapabilities(
            tool_use=True,
            vision=False,
            streaming=True,
            function_calling=True,
        ),
    ),
    (
        re.compile(r"gemini"),
        ModelCapabilities(
            tool_use=True,
            vision=True,
            streaming=True,
            function_calling=True,
        ),
    ),
    (
        re.compile(r"o[0-9]"),
        ModelCapabilities(
            tool_use=True,
            vision=True,
            streaming=False,
            function_calling=True,
        ),
    ),
    (
        re.compile(r"llama|mistral|mixtral|phi|qwen|deepseek|command"),
        ModelCapabilities(
            tool_use=True,
            vision=False,
            streaming=True,
            function_calling=True,
        ),
    ),
]


class CapabilityProbe:
    """Probes and caches model capabilities.

    Uses a heuristic table (fast, primary), then pattern matching for
    unknown models, and optionally a runtime probe (slow, opt-in).

    Args:
        enable_runtime_probe: Whether to send actual test API calls to
            verify capabilities for unknown models. Disabled by default
            because it costs tokens and adds latency.
        max_cache_entries: Maximum number of (provider, model) pairs to
            cache. Oldest entries evicted when full.
    """

    def __init__(
        self,
        enable_runtime_probe: bool = False,
        max_cache_entries: int = 256,
    ) -> None:
        self._enable_runtime_probe = enable_runtime_probe
        self._cache: OrderedDict[tuple[str, str], ModelCapabilities] = OrderedDict()
        self._max_cache_entries = max_cache_entries

    async def discover(
        self,
        provider_name: str,
        model_id: str,
        provider_defaults: ModelCapabilities | None = None,
    ) -> ModelCapabilities:
        """Return capabilities for a model+provider combination.

        Resolution order:
        1. Cache hit
        2. Heuristic table (exact match)
        3. Pattern matching
        4. Runtime probe (opt-in, requires ``provider_instance``)
        5. Provider-level defaults

        Args:
            provider_name: Provider name (e.g. ``"openai_compatible"``).
            model_id: Model identifier (e.g. ``"gpt-4o"``).
            provider_defaults: Fallback capabilities when nothing else matches.

        Returns:
            Detected ModelCapabilities.
        """
        key = (provider_name, model_id)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        caps = self._lookup(model_id)
        if caps is not None:
            self._set_cache(key, caps)
            return caps

        if provider_defaults is not None:
            self._set_cache(key, provider_defaults)
            return provider_defaults

        fallback = ModelCapabilities(
            tool_use=False,
            vision=False,
            streaming=True,
            function_calling=False,
        )
        self._set_cache(key, fallback)
        return fallback

    def _lookup(self, model_id: str) -> ModelCapabilities | None:
        model_lower = model_id.lower()

        exact = _SUPPORTED_MODELS.get(model_lower)
        if exact is not None:
            return exact

        for pattern, caps in _PATTERNS:
            if pattern.search(model_lower):
                return caps

        return None

    def invalidate(
        self,
        provider_name: str | None = None,
        model_id: str | None = None,
    ) -> None:
        """Clear cache entries.

        Args:
            provider_name: If set, only invalidate entries for this provider.
            model_id: If set, only invalidate entries for this model.
                Requires ``provider_name`` also set.
        """
        if provider_name is None:
            self._cache.clear()
            return
        if model_id is None:
            keys = [k for k in self._cache if k[0] == provider_name]
            for k in keys:
                del self._cache[k]
            return
        self._cache.pop((provider_name, model_id), None)

    def _set_cache(self, key: tuple[str, str], caps: ModelCapabilities) -> None:
        while len(self._cache) >= self._max_cache_entries:
            self._cache.popitem(last=False)
        self._cache[key] = caps


def strip_unsupported(
    messages: list[ChatMessage],
    tools: list[dict[str, Any]] | None,
    capabilities: ModelCapabilities,
) -> tuple[list[ChatMessage], list[dict[str, Any]] | None]:
    """Gracefully degrade messages and tools for a model's capabilities.

    Strips ``ImagePart`` from messages when vision is not supported.
    Strips tool definitions and adds a system message when tool use or
    function calling is not supported.

    Args:
        messages: Original chat messages.
        tools: Original tool definitions.
        capabilities: Target model's capabilities.

    Returns:
        A ``(messages, tools)`` tuple with unsupported features removed.
    """
    p_messages = messages
    p_tools = tools

    if tools and not (capabilities.tool_use or capabilities.function_calling):
        p_tools = None
        p_messages = list(p_messages)
        p_messages.insert(
            0,
            ChatMessage.system(
                "You do not have access to tools or function calling. "
                "Respond as a text-only assistant."
            ),
        )

    if not capabilities.vision:
        p_messages = _strip_vision(p_messages)

    return p_messages, p_tools


def _strip_vision(messages: list[ChatMessage]) -> list[ChatMessage]:
    result: list[ChatMessage] = []
    for msg in messages:
        if not isinstance(msg.content, list):
            result.append(msg)
            continue
        text_parts: list[str] = []
        image_count = 0
        for part in msg.content:
            if isinstance(part, ImagePart):
                image_count += 1
            elif hasattr(part, "text"):
                text_parts.append(str(part.text))
        if image_count:
            combined = " ".join(p for p in text_parts if p)
            if combined:
                combined += "\n[image omitted]"
            else:
                combined = f"[{image_count} image(s) omitted]"
            result.append(ChatMessage(role=msg.role, content=combined))
        else:
            result.append(msg)
    return result


def tool_to_provider(
    tools: list[dict[str, Any]],
    provider: str,
) -> list[dict[str, Any]]:
    """Convert canonical tool schemas to provider-native format.

    Canonical format (OpenAI style)::

        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {...}
            }
        }

    Args:
        tools: Canonical tool schemas.
        provider: Target provider name (``"openai_compatible"``,
            ``"anthropic"``, ``"gemini"``).

    Returns:
        Tools in provider-native format.
    """
    if provider == "anthropic":
        converted: list[dict[str, Any]] = []
        for tool in tools:
            fn = tool.get("function", tool)
            converted.append(
                {
                    "name": fn.get("name", "unknown"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                }
            )
        return converted

    if provider == "gemini":
        declarations: list[dict[str, Any]] = []
        for tool in tools:
            fn = tool.get("function", tool)
            declarations.append(
                {
                    "name": fn.get("name", "unknown"),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                }
            )
        return [{"functionDeclarations": declarations}]

    return tools


def tool_call_to_canonical(
    tool_calls: list[dict[str, Any]],
    provider: str,
) -> list[dict[str, Any]]:
    """Convert provider-native tool calls to canonical format.

    Canonical format (OpenAI style)::

        {
            "id": "...",
            "type": "function",
            "function": {
                "name": "...",
                "arguments": "{...}"   # JSON string
            }
        }

    Args:
        tool_calls: Provider-native tool call list.
        provider: Source provider name.

    Returns:
        Tool calls in canonical format.
    """
    if provider == "gemini":
        canonical: list[dict[str, Any]] = []
        for tc in tool_calls:
            fn_name = tc.get("name", "")
            fn_args = tc.get("args", tc.get("arguments", {}))
            canonical.append(
                {
                    "id": fn_name,
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "arguments": json.dumps(fn_args)
                        if isinstance(fn_args, dict)
                        else str(fn_args),
                    },
                }
            )
        return canonical

    if provider == "anthropic":
        result: list[dict[str, Any]] = []
        for tc in tool_calls:
            tc_id = tc.get("id", "")
            tc_name = tc.get("name", "")
            tc_input = tc.get("input", {})
            args_str: str = json.dumps(tc_input) if isinstance(tc_input, dict) else str(tc_input)
            result.append(
                {
                    "id": tc_id,
                    "type": "function",
                    "function": {
                        "name": tc_name,
                        "arguments": args_str,
                    },
                }
            )
        return result

    return tool_calls
