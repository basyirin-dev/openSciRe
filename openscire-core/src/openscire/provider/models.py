# SPDX-License-Identifier: Apache-2.0

"""Data models for provider-layer chat, streaming chunks, and capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FinishReason(StrEnum):
    """Standardized finish reasons for streaming completions."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    NULL = "null"


@dataclass
class TextPart:
    """A text content part for multi-modal messages."""

    type: str = "text"
    text: str = ""


@dataclass
class ImagePart:
    """An image URL content part for multi-modal (vision) messages."""

    type: str = "image_url"
    image_url: dict[str, str] | None = None

    @classmethod
    def from_url(cls, url: str, detail: str | None = None) -> ImagePart:
        d: dict[str, str] = {"url": url}
        if detail:
            d["detail"] = detail
        return cls(image_url=d)


ContentPart = TextPart | ImagePart


@dataclass
class ProviderMetrics:
    """Metrics for a single provider invocation."""

    provider_name: str = ""
    model_name: str = ""
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


@dataclass
class ChatMessage:
    """A message in a chat conversation with role, content, and optional tool data."""

    role: str
    content: str | list[ContentPart] = ""
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": self.role}
        if isinstance(self.content, list):
            msg["content"] = [{"type": p.type, **self._part_kwargs(p)} for p in self.content]
        elif self.content:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
            if isinstance(self.content, list) or not self.content:
                msg["content"] = ""
            else:
                msg["content"] = self.content
        return msg

    @staticmethod
    def _part_kwargs(part: ContentPart) -> dict[str, Any]:
        if isinstance(part, TextPart):
            return {"text": part.text}
        if isinstance(part, ImagePart):
            return {"image_url": part.image_url} if part.image_url else {}
        return {}

    @classmethod
    def system(cls, content: str | list[ContentPart]) -> ChatMessage:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str | list[ContentPart]) -> ChatMessage:
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls, content: str = "", tool_calls: list[dict[str, Any]] | None = None
    ) -> ChatMessage:
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, content: str, tool_call_id: str) -> ChatMessage:
        return cls(role="tool", content=content, tool_call_id=tool_call_id)


@dataclass
class FallbackInfo:
    """Metadata about a fallback event in a cascade chain."""

    step_index: int = 0
    total_steps: int = 0
    attempted_provider: str = ""
    attempted_model: str = ""
    error_message: str = ""
    error_code: str = ""
    latency_ms: float = 0.0


@dataclass
class Chunk:
    """A streaming response chunk with optional tool calls, metrics, and fallback info."""

    delta_content: str = ""
    finish_reason: FinishReason | None = None
    usage: ProviderMetrics | None = None
    tool_calls: list[dict[str, Any]] | None = None
    provider_metrics: ProviderMetrics | None = None
    thinking: str | None = None
    fallback_info: FallbackInfo | None = None
    logprobs: dict[str, float] | None = None
    top_logprobs: list[dict[str, float]] | None = None


@dataclass
class ModelCapabilities:
    """Capability flags for an LLM model."""

    tool_use: bool = False
    vision: bool = False
    streaming: bool = True
    function_calling: bool = False


@dataclass
class ModelInfo:
    """Metadata about a specific model available from a provider."""

    id: str
    name: str = ""
    provider: str = ""
    context_window: int = 4096
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    quantization: str | None = None
    pricing_per_1k_input: float = 0.0
    pricing_per_1k_output: float = 0.0


@dataclass
class ModelCard:
    """Disclosure card with training summary, biases, evaluations, and safety ratings."""

    provider: str = ""
    training_data_summary: str = ""
    known_biases: list[str] = field(default_factory=list)
    evaluation_results: dict[str, Any] = field(default_factory=dict)
    intended_use: str = ""
    limitations: list[str] = field(default_factory=list)
    safety_ratings: dict[str, str] = field(default_factory=dict)
