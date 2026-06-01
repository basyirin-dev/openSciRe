# SPDX-License-Identifier: Apache-2.0

"""Anthropic Claude provider adapter with extended thinking and tool use."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from openscire.provider.base import ModelProvider, ProviderConfig
from openscire.provider.models import (
    ChatMessage,
    Chunk,
    ContentPart,
    FinishReason,
    ImagePart,
    ModelCapabilities,
    ModelCard,
    ModelInfo,
    ProviderMetrics,
    TextPart,
)

_ANTHROPIC_VERSION = "2023-06-01"

_KNOWN_MODELS: list[dict[str, Any]] = [
    {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "context": 200000},
    {"id": "claude-opus-4-20250514", "name": "Claude Opus 4", "context": 200000},
    {"id": "claude-haiku-3-5-20241022", "name": "Claude Haiku 3.5", "context": 200000},
    {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "context": 200000},
    {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "context": 200000},
    {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "context": 200000},
    {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "context": 200000},
    {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "context": 200000},
    {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "context": 200000},
]


def _guess_context_window(model_id: str) -> int:
    model_lower = model_id.lower()
    if "claude" not in model_lower:
        return 4096
    for entry in _KNOWN_MODELS:
        if entry["id"] in model_id:
            ctx: int = entry["context"]
            return ctx
    return 100000


def _stop_reason_to_finish_reason(reason: str | None) -> FinishReason | None:
    if reason is None:
        return None
    mapping: dict[str, FinishReason] = {
        "end_turn": FinishReason.STOP,
        "stop_sequence": FinishReason.STOP,
        "max_tokens": FinishReason.LENGTH,
        "tool_use": FinishReason.TOOL_CALLS,
        "content_filtered": FinishReason.CONTENT_FILTER,
    }
    return mapping.get(reason, FinishReason.STOP)


def _convert_content_parts(parts: list[ContentPart]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for part in parts:
        if isinstance(part, TextPart):
            result.append({"type": "text", "text": part.text})
        elif isinstance(part, ImagePart):
            if part.image_url and "url" in part.image_url:
                result.append(
                    {
                        "type": "image",
                        "source": {"type": "url", "url": part.image_url["url"]},
                    }
                )
            elif part.image_url:
                result.append(
                    {
                        "type": "image",
                        "source": {"type": "url", **part.image_url},
                    }
                )
    return result


def _convert_messages(
    messages: list[ChatMessage],
) -> tuple[str | None, list[dict[str, Any]]]:
    system: str | None = None
    anthropic_messages: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == "system":
            if isinstance(msg.content, list):
                parts = _convert_content_parts(msg.content)
                text_parts = [p["text"] for p in parts if p.get("type") == "text"]
                system = "\n".join(text_parts) if text_parts else ""
            elif msg.content:
                system = msg.content
            continue

        if msg.role == "tool":
            anthropic_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id or "",
                            "content": msg.content if isinstance(msg.content, str) else "",
                        }
                    ],
                }
            )
            continue

        content_list: list[dict[str, Any]] = []
        if isinstance(msg.content, list):
            content_list = _convert_content_parts(msg.content)
        elif msg.content:
            content_list = [{"type": "text", "text": msg.content}]
        else:
            content_list = [{"type": "text", "text": ""}]

        if msg.role == "assistant" and msg.tool_calls:
            for tc in msg.tool_calls:
                content_list.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("function", {}).get("name", ""),
                        "input": {},
                    }
                )

        anthropic_messages.append({"role": msg.role, "content": content_list})

    return system, anthropic_messages


class AnthropicProvider(ModelProvider):
    """Provider adapter for Anthropic's Messages API (Claude models)."""

    PROVIDER_NAME = "anthropic"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config)
        base = self._config.base_url.rstrip("/") or "https://api.anthropic.com"
        self._messages_url = f"{base}/v1/messages"
        self._client = httpx.AsyncClient(timeout=self._config.timeout)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        if self._config.api_key:
            headers["x-api-key"] = self._config.api_key.get_secret_value()
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
            self._messages_url,
            headers=self._headers(),
            json=payload,
        )
        response.encoding = "utf-8"

        if response.status_code != 200:
            error_detail = _extract_error(response)
            raise _map_http_error(response.status_code, error_detail)

        async for chunk in self._parse_events(response):
            yield chunk

        elapsed = (time.monotonic() - start) * 1000
        yield Chunk(
            provider_metrics=ProviderMetrics(
                provider_name=self.PROVIDER_NAME,
                model_name=self._config.default_model,
                latency_ms=elapsed,
            )
        )

    async def list_models(self) -> list[ModelInfo]:
        if self._config.default_model:
            ctx = _guess_context_window(self._config.default_model)
            return [
                ModelInfo(
                    id=self._config.default_model,
                    name=self._config.default_model,
                    provider=self.PROVIDER_NAME,
                    context_window=ctx,
                    capabilities=self.get_capabilities(self._config.default_model),
                )
            ]
        return [
            ModelInfo(
                id=entry["id"],
                name=entry["name"],
                provider=self.PROVIDER_NAME,
                context_window=entry["context"],
                capabilities=self.get_capabilities(entry["id"]),
            )
            for entry in _KNOWN_MODELS
        ]

    def get_capabilities(self, model_id: str | None = None) -> ModelCapabilities:
        model_lower = (model_id or self._config.default_model or "").lower()
        return ModelCapabilities(
            tool_use=True,
            vision="haiku" not in model_lower,
            streaming=True,
            function_calling=True,
        )

    def supports_tool_use(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    async def get_token_count(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def get_context_window(self) -> int:
        return _guess_context_window(self._config.default_model)

    async def get_model_card(self) -> ModelCard:
        return ModelCard(
            provider=self.PROVIDER_NAME,
            intended_use=(
                "General-purpose chat, code generation, analysis, and tool use"
                " via Anthropic's Claude models"
            ),
            limitations=[
                "May produce plausible-sounding but incorrect information",
                "Training data cutoff varies by model version",
                "Extended thinking mode increases latency significantly",
                "Not suitable for real-time safety-critical decisions",
            ],
            training_data_summary=(
                "Trained on a diverse corpus of internet text, books, and"
                " code up to the model's knowledge cutoff date"
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
        system, converted = _convert_messages(messages)
        payload: dict[str, Any] = {
            "model": self._config.default_model or "claude-sonnet-4-20250514",
            "max_tokens": max_tokens or 8192,
            "messages": converted,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = self._convert_tools(tools)
        return payload

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

    async def _parse_events(self, response: httpx.Response) -> AsyncIterator[Chunk]:
        event_type = ""
        buffer = ""
        pending_tool_use: dict[str, Any] | None = None
        accumulated_thinking: str | None = None
        usage: ProviderMetrics | None = None

        async for byte_chunk in response.aiter_bytes():
            buffer += byte_chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip("\r")

                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: ") and event_type:
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    event_data = data

                    if event_type == "message_start":
                        msg_data = event_data.get("message", {})
                        if msg_data.get("usage"):
                            u = msg_data["usage"]
                            usage = ProviderMetrics(
                                prompt_tokens=u.get("input_tokens", 0),
                            )

                    elif event_type == "content_block_start":
                        block = event_data.get("content_block", {})
                        block_type = block.get("type")
                        if block_type == "thinking":
                            accumulated_thinking = block.get("thinking", "")
                        elif block_type == "tool_use":
                            pending_tool_use = {
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": "",
                                },
                            }

                    elif event_type == "content_block_delta":
                        delta = event_data.get("delta", {})
                        delta_type = delta.get("type")
                        if delta_type == "text_delta":
                            yield Chunk(delta_content=delta.get("text", ""))
                        elif delta_type == "thinking_delta":
                            thinking_text = delta.get("thinking", "")
                            if accumulated_thinking is None:
                                accumulated_thinking = thinking_text
                            else:
                                accumulated_thinking += thinking_text
                            yield Chunk(thinking=thinking_text)
                        elif delta_type == "input_json_delta" and pending_tool_use:
                            args = pending_tool_use["function"]["arguments"]
                            pending_tool_use["function"]["arguments"] = args + delta.get(
                                "partial_json", ""
                            )

                    elif event_type == "content_block_stop":
                        if pending_tool_use:
                            args_str = pending_tool_use["function"]["arguments"]
                            try:
                                parsed = json.loads(args_str) if args_str else {}
                            except json.JSONDecodeError:
                                parsed = {"raw": args_str}
                            pending_tool_use["function"]["arguments"] = parsed
                            yield Chunk(tool_calls=[pending_tool_use])
                            pending_tool_use = None

                    elif event_type == "message_delta":
                        delta = event_data.get("delta", {})
                        stop_reason = delta.get("stop_reason")
                        if stop_reason:
                            yield Chunk(
                                finish_reason=_stop_reason_to_finish_reason(stop_reason),
                            )
                        if event_data.get("usage"):
                            u = event_data["usage"]
                            out = u.get("output_tokens", 0)
                            if usage is None:
                                usage = ProviderMetrics(completion_tokens=out)
                            else:
                                usage.completion_tokens = out
                                usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

                    elif event_type == "message_stop":
                        if usage and usage.total_tokens == 0:
                            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                        if usage and not usage.model_name:
                            usage.model_name = self._config.default_model
                        if usage:
                            yield Chunk(usage=usage)

                    event_type = ""


def _extract_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        err = body.get("error", {})
        msg: object = err.get("message", str(response.status_code))
        return str(msg)
    except (json.JSONDecodeError, ValueError, AttributeError):
        return response.text[:200]


def _map_http_error(status: int, detail: str) -> Exception:
    from openscire.constants import ErrorCode
    from openscire.exceptions import ModelProviderError

    if status == 401:
        return ModelProviderError(
            f"Authentication failed: {detail}",
            source="provider.anthropic_adapter",
            error_code=ErrorCode.MODEL_AUTH_FAILURE,
        )
    if status == 429:
        return ModelProviderError(
            f"Rate limited: {detail}",
            source="provider.anthropic_adapter",
            error_code=ErrorCode.MODEL_RATE_LIMIT,
        )
    if status in {502, 503, 504}:
        return ModelProviderError(
            f"Provider unavailable ({status}): {detail}",
            source="provider.anthropic_adapter",
            error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
        )
    return ModelProviderError(
        f"API error {status}: {detail}",
        source="provider.anthropic_adapter",
        error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
    )
