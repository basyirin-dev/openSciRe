# SPDX-License-Identifier: Apache-2.0

"""Google Gemini provider adapter with streaming and vision support."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from openscire.provider.base import HealthStatus, ModelProvider, ProviderConfig
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

_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"

_KNOWN_MODELS: dict[str, int] = {
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.5-flash": 1_048_576,
    "gemini-2.0-flash": 1_048_576,
    "gemini-1.5-pro": 2_097_152,
    "gemini-1.5-flash": 1_048_576,
}

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "STOP": FinishReason.STOP,
    "MAX_TOKENS": FinishReason.LENGTH,
    "SAFETY": FinishReason.CONTENT_FILTER,
    "RECITATION": FinishReason.CONTENT_FILTER,
    "MALFORMED_FUNCTION_CALL": FinishReason.ERROR,
    "PROHIBITED_CONTENT": FinishReason.CONTENT_FILTER,
    "SPII": FinishReason.CONTENT_FILTER,
    "BLOCKLIST": FinishReason.CONTENT_FILTER,
    "OTHER": FinishReason.CONTENT_FILTER,
}


def _guess_context_window(model_id: str) -> int:
    model_lower = model_id.lower()
    for prefix, ctx in _KNOWN_MODELS.items():
        if model_lower.startswith(prefix):
            return ctx
    if "gemini" in model_lower:
        return 1_048_576
    return 4096


def _gemini_finish_reason(reason: str | None) -> FinishReason | None:
    if reason is None:
        return None
    return _FINISH_REASON_MAP.get(reason, FinishReason.STOP)


def _convert_parts(parts: list[ContentPart]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for part in parts:
        if isinstance(part, TextPart):
            result.append({"text": part.text})
        elif isinstance(part, ImagePart) and part.image_url:
            url = part.image_url.get("url", "")
            result.append(
                {
                    "inlineData": {"mimeType": "image/jpeg", "data": url},
                }
            )
    return result


def _convert_messages(
    messages: list[ChatMessage],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    system_parts: list[dict[str, Any]] = []
    gemini_contents: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == "system":
            if isinstance(msg.content, list):
                for p in _convert_parts(msg.content):
                    if "text" in p:
                        system_parts.append(p)
            elif msg.content:
                system_parts.append({"text": msg.content})
            continue

        parts: list[dict[str, Any]] = []
        if isinstance(msg.content, list):
            parts = _convert_parts(msg.content)
        elif msg.content:
            parts = [{"text": msg.content}]

        if msg.role == "assistant" and msg.tool_calls:
            for tc in msg.tool_calls:
                fn = tc.get("function", {})
                parts.append(
                    {
                        "functionCall": {
                            "name": fn.get("name", ""),
                            "args": fn.get("arguments", {}),
                        },
                    }
                )

        role = "model" if msg.role == "assistant" else msg.role
        gemini_contents.append({"role": role, "parts": parts})

    return system_parts, gemini_contents


def _extract_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        err: dict[str, Any] = body.get("error", body)
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
            source="provider.gemini_adapter",
            error_code=ErrorCode.MODEL_AUTH_FAILURE,
        )
    if status == 429:
        return ModelProviderError(
            f"Rate limited: {detail}",
            source="provider.gemini_adapter",
            error_code=ErrorCode.MODEL_RATE_LIMIT,
        )
    if status in {502, 503, 504}:
        return ModelProviderError(
            f"Provider unavailable ({status}): {detail}",
            source="provider.gemini_adapter",
            error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
        )
    return ModelProviderError(
        f"API error {status}: {detail}",
        source="provider.gemini_adapter",
        error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
    )


class GeminiProvider(ModelProvider):
    """Provider adapter for Google Gemini API via raw httpx."""

    PROVIDER_NAME = "gemini"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config)
        base = self._config.base_url.rstrip("/") or _DEFAULT_BASE_URL
        model = self._config.default_model or "gemini-2.0-flash"
        self._stream_url = f"{base}/v1beta/models/{model}:streamGenerateContent?alt=sse"
        self._models_url = f"{base}/v1beta/models"
        self._client = httpx.AsyncClient(timeout=self._config.timeout)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._config.api_key:
            headers["x-goog-api-key"] = self._config.api_key.get_secret_value()
        headers.update(self._config.extra_headers)
        return headers

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,  # noqa: ARG002
    ) -> AsyncIterator[Chunk]:
        payload = self._build_payload(messages, tools, temperature, max_tokens)
        start = time.monotonic()

        response = await self._client.post(
            self._stream_url,
            headers=self._headers(),
            json=payload,
        )
        response.encoding = "utf-8"

        if response.status_code != 200:
            error_detail = _extract_error(response)
            raise _map_http_error(response.status_code, error_detail)

        async for chunk in self._parse_sse(response):
            yield chunk

        elapsed = (time.monotonic() - start) * 1000
        yield Chunk(
            provider_metrics=ProviderMetrics(
                provider_name=self.PROVIDER_NAME,
                model_name=self._config.default_model or "gemini-2.0-flash",
                latency_ms=elapsed,
            )
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            response = await self._client.get(
                self._models_url,
                headers=self._headers(),
                params={"filter": "generateContent"},
            )
            if response.status_code == 200:
                data = response.json()
                models_list: list[ModelInfo] = []
                for item in data.get("models", data.get("data", [])):
                    mid: str = item.get("name", item.get("id", "")).split("/")[-1]
                    if not mid:
                        mid = item.get("displayName", "unknown")
                    models_list.append(
                        ModelInfo(
                            id=mid,
                            name=mid,
                            provider=self.PROVIDER_NAME,
                            context_window=_guess_context_window(mid),
                            capabilities=self.get_capabilities(mid),
                        )
                    )
                if models_list:
                    return models_list
        except Exception:
            pass
        return [self._default_model_info()]

    def get_capabilities(self, model_id: str | None = None) -> ModelCapabilities:
        model_lower = (model_id or self._config.default_model or "gemini-2.0-flash").lower()
        return ModelCapabilities(
            tool_use=True,
            streaming=True,
            vision="flash-lite" not in model_lower,
            function_calling=True,
        )

    def supports_tool_use(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    async def get_token_count(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def get_context_window(self) -> int:
        return _guess_context_window(self._config.default_model or "gemini-2.0-flash")

    async def health(self) -> HealthStatus:
        start = time.monotonic()
        try:
            resp = await self._client.get(
                self._models_url,
                headers=self._headers(),
                params={"pageSize": 1},
            )
            if resp.status_code == 200:
                elapsed = (time.monotonic() - start) * 1000
                return HealthStatus(ok=True, latency_ms=elapsed)
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(
                ok=False,
                latency_ms=elapsed,
                error=_extract_error(resp),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(
                ok=False,
                latency_ms=elapsed,
                error=str(exc),
            )

    async def get_model_card(self) -> ModelCard:
        return ModelCard(
            provider=self.PROVIDER_NAME,
            intended_use=(
                "Multimodal chat, code generation, analysis, vision,"
                " and tool use via Google's Gemini models"
            ),
            limitations=[
                "May produce plausible-sounding but incorrect information",
                "Training data cutoff varies by model version",
                "Vision capabilities depend on inline image encoding",
                "Not suitable for real-time safety-critical decisions",
            ],
            training_data_summary=(
                "Trained on a diverse corpus of internet text, code, images, audio, and video"
            ),
            safety_ratings={
                "harassment": "unknown",
                "hate_speech": "unknown",
                "sexually_explicit": "unknown",
                "dangerous_content": "unknown",
            },
        )

    def _build_payload(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        system_parts, gemini_contents = _convert_messages(messages)
        payload: dict[str, Any] = {"contents": gemini_contents}
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        gen_config: dict[str, Any] = {}
        if temperature is not None:
            gen_config["temperature"] = temperature
        if max_tokens is not None:
            gen_config["maxOutputTokens"] = max_tokens
        if gen_config:
            payload["generationConfig"] = gen_config
        if tools:
            payload["tools"] = self._convert_tools(tools)
        return payload

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    for c in self._parse_response(data):
                        yield c

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> list[Chunk]:
        results: list[Chunk] = []
        candidates = data.get("candidates")
        if not candidates:
            return results
        candidate = candidates[0]
        content = candidate.get("content", {})
        parts: list[dict[str, Any]] = content.get("parts", [])

        for part in parts:
            if "text" in part:
                if part.get("thought", False):
                    results.append(Chunk(thinking=part["text"]))
                else:
                    results.append(Chunk(delta_content=part["text"]))
            if "functionCall" in part:
                fc = part["functionCall"]
                results.append(
                    Chunk(
                        tool_calls=[
                            {
                                "id": fc.get("name", ""),
                                "type": "function",
                                "function": {
                                    "name": fc.get("name", ""),
                                    "arguments": fc.get("args", {}),
                                },
                            }
                        ]
                    )
                )

        finish = candidate.get("finishReason")
        if finish:
            results.append(
                Chunk(
                    finish_reason=_gemini_finish_reason(finish),
                )
            )

        usage = data.get("usageMetadata")
        if usage:
            results.append(
                Chunk(
                    usage=ProviderMetrics(
                        prompt_tokens=usage.get("promptTokenCount", 0),
                        completion_tokens=usage.get("candidatesTokenCount", 0),
                        total_tokens=usage.get("totalTokenCount", 0),
                    )
                )
            )

        return results

    def _default_model_info(self) -> ModelInfo:
        mid = self._config.default_model or "gemini-2.0-flash"
        return ModelInfo(
            id=mid,
            name=mid,
            provider=self.PROVIDER_NAME,
            context_window=_guess_context_window(mid),
            capabilities=self.get_capabilities(mid),
        )
