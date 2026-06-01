# SPDX-License-Identifier: Apache-2.0

"""OpenAI-compatible provider adapter with streaming and tool use."""

from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from openscire.provider.base import ModelProvider, ProviderConfig
from openscire.provider.models import (
    ChatMessage,
    Chunk,
    FinishReason,
    ModelCapabilities,
    ModelCard,
    ModelInfo,
    ProviderMetrics,
)
from openscire.provider.quantization import detect_from_name


class OpenAICompatibleProvider(ModelProvider):
    """Provider adapter for any OpenAI-compatible API endpoint (OpenAI, LiteLLM, vLLM, etc.)."""

    PROVIDER_NAME = "openai_compatible"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config)
        base = self._config.base_url.rstrip("/")
        self._chat_url = f"{base}/chat/completions" if base else ""
        self._models_url = f"{base}/models" if base else ""
        self._client = httpx.AsyncClient(timeout=self._config.timeout)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key.get_secret_value()}"
        headers.update(self._config.extra_headers)
        return headers

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        _ = provenance_parent_id

        payload = self._build_payload(messages, tools, temperature, max_tokens)
        start = time.monotonic()

        response = await self._client.post(
            self._chat_url,
            headers=self._headers(),
            json=payload,
        )
        response.encoding = "utf-8"

        if response.status_code != 200:
            error_detail = _extract_error(response)
            raise _map_http_error(response.status_code, error_detail)

        if payload.get("stream"):
            async for chunk in self._parse_sse(response):
                yield chunk
        else:
            yield self._parse_non_streaming(response)

        elapsed = (time.monotonic() - start) * 1000
        final_chunk = Chunk(
            provider_metrics=ProviderMetrics(
                provider_name=self.PROVIDER_NAME,
                model_name=self._config.default_model,
                latency_ms=elapsed,
            )
        )
        yield final_chunk

    async def list_models(self) -> list[ModelInfo]:
        if not self._models_url:
            return [self._default_model_info()]

        response = await self._client.get(self._models_url, headers=self._headers())
        response.encoding = "utf-8"

        if response.status_code != 200:
            return [self._default_model_info()]

        data = response.json()
        models: list[ModelInfo] = []
        for item in data.get("data", []):
            model_id = item.get("id", "unknown")
            quant = detect_from_name(model_id)
            models.append(
                ModelInfo(
                    id=model_id,
                    name=model_id,
                    provider=self.PROVIDER_NAME,
                    context_window=_guess_context_window(model_id),
                    quantization=quant.level if quant else None,
                )
            )
        return models or [self._default_model_info()]

    def supports_tool_use(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    def get_capabilities(self, model_id: str | None = None) -> ModelCapabilities:
        return _openai_capabilities_for_model(
            model_id or self._config.default_model or "",
        )

    async def get_token_count(self, text: str) -> int:
        try:
            import tiktoken

            model = self._config.default_model
            if model:
                encoding = tiktoken.encoding_for_model(model)
            else:
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except (ImportError, KeyError, Exception):
            return max(1, len(text) // 4)

    async def get_context_window(self) -> int:
        return _guess_context_window(self._config.default_model)

    async def get_model_card(self) -> ModelCard:
        return ModelCard(
            provider=self.PROVIDER_NAME,
            intended_use=(
                "General-purpose chat, code generation, and tool use via OpenAI-compatible API"
            ),
            limitations=[
                "Model-specific limitations vary by provider",
                "Factual accuracy depends on the underlying model",
                "May produce plausible-sounding but incorrect information",
                "Context window depends on the specific model deployed",
            ],
            training_data_summary=(
                "Training data varies by provider; check the provider's documentation"
            ),
            safety_ratings={
                "self_harm": "unknown",
                "hate_speech": "unknown",
                "sexual_content": "unknown",
                "violence": "unknown",
            },
        )

    def _build_payload(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._config.default_model or "gpt-3.5-turbo",
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    async def _parse_sse(self, response: httpx.Response) -> AsyncIterator[Chunk]:
        buffer = ""
        async for byte_chunk in response.aiter_bytes():
            buffer += byte_chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    chunk = _parse_sse_chunk(data)
                    if chunk is not None:
                        yield chunk

    def _parse_non_streaming(self, response: httpx.Response) -> Chunk:
        data = response.json()
        choice = data.get("choices", [{}])[0]
        delta = choice.get("message", choice.get("delta", {}))
        content = delta.get("content", "")
        finish = choice.get("finish_reason")
        usage_data = data.get("usage")
        metrics: ProviderMetrics | None = None
        if usage_data:
            metrics = ProviderMetrics(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
        return Chunk(
            delta_content=content or "",
            finish_reason=FinishReason(finish) if finish else None,
            usage=metrics,
        )

    def _default_model_info(self) -> ModelInfo:
        return ModelInfo(
            id=self._config.default_model or "unknown",
            name=self._config.default_model or "unknown",
            provider=self.PROVIDER_NAME,
            context_window=_guess_context_window(self._config.default_model),
        )


def _guess_context_window(model_id: str) -> int:
    model_lower = model_id.lower()
    if "128k" in model_lower:
        return 128000
    if "200k" in model_lower:
        return 200000
    if "1m" in model_lower or "1-m" in model_lower:
        return 1048576
    if "32k" in model_lower:
        return 32768
    if "16k" in model_lower:
        return 16384
    if "gpt-4" in model_lower:
        return 8192
    if "gpt-3.5" in model_lower:
        return 16384
    if "claude" in model_lower:
        return 100000
    if "llama" in model_lower or "llm" in model_lower:
        return 8192
    return 4096


def _parse_sse_chunk(data: dict[str, Any]) -> Chunk | None:
    choices = data.get("choices")
    if not choices:
        return None
    choice = choices[0]
    delta = choice.get("delta", {})
    content = delta.get("content", "")
    tool_calls_delta = delta.get("tool_calls")
    finish = choice.get("finish_reason")
    usage_data = data.get("usage")
    metrics: ProviderMetrics | None = None
    if usage_data:
        metrics = ProviderMetrics(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
    tool_calls: list[dict[str, Any]] | None = None
    if tool_calls_delta:
        tool_calls = tool_calls_delta
    return Chunk(
        delta_content=content,
        finish_reason=FinishReason(finish) if finish else None,
        usage=metrics,
        tool_calls=tool_calls,
    )


def _extract_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        msg: object = body.get("error", {}).get("message", str(response.status_code))
        return str(msg)
    except (json.JSONDecodeError, ValueError, AttributeError):
        return response.text[:200]


def _map_http_error(status: int, detail: str) -> Exception:
    from openscire.constants import ErrorCode
    from openscire.exceptions import ModelProviderError

    if status == 401:
        return ModelProviderError(
            f"Authentication failed: {detail}",
            source="provider.openai_adapter",
            error_code=ErrorCode.MODEL_AUTH_FAILURE,
        )
    if status == 429:
        return ModelProviderError(
            f"Rate limited: {detail}",
            source="provider.openai_adapter",
            error_code=ErrorCode.MODEL_RATE_LIMIT,
        )
    if status in {502, 503, 504}:
        return ModelProviderError(
            f"Provider unavailable ({status}): {detail}",
            source="provider.openai_adapter",
            error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
        )
    return ModelProviderError(
        f"API error {status}: {detail}",
        source="provider.openai_adapter",
        error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
    )


def _openai_capabilities_for_model(model_id: str) -> ModelCapabilities:
    """Return capabilities for an OpenAI-compatible model using heuristics."""
    model_lower = model_id.lower()
    exact = _OPENAI_CAP_TABLE.get(model_lower)
    if exact is not None:
        return exact
    for pattern, caps in _OPENAI_CAP_PATTERNS:
        if pattern.search(model_lower):
            return caps
    return ModelCapabilities(tool_use=True, vision=False, streaming=True, function_calling=True)


_OPENAI_CAP_TABLE: dict[str, ModelCapabilities] = {
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
    "gpt-3.5-turbo": ModelCapabilities(
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
}

_OPENAI_CAP_PATTERNS: list[tuple[re.Pattern[str], ModelCapabilities]] = [
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
        re.compile(r"o[0-9]"),
        ModelCapabilities(
            tool_use=True,
            vision=True,
            streaming=False,
            function_calling=True,
        ),
    ),
    (
        re.compile(r"claude"),
        ModelCapabilities(
            tool_use=True,
            vision=True,
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
        re.compile(r"llama|mistral|mixtral|phi|qwen|deepseek"),
        ModelCapabilities(
            tool_use=True,
            vision=False,
            streaming=True,
            function_calling=True,
        ),
    ),
]
