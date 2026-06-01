# SPDX-License-Identifier: Apache-2.0

"""Abstract base provider interface and configuration models."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Protocol

from pydantic import BaseModel, Field, SecretStr

from openscire.provider.models import (
    ChatMessage,
    Chunk,
    ModelCapabilities,
    ModelCard,
    ModelInfo,
    ProviderMetrics,
)

logger = logging.getLogger(__name__)


class _ProvenanceTrackerProtocol(Protocol):
    """Minimal protocol for provenance trackers used by providers."""

    def track(
        self,
        action_type: str,
        model_id: str = "",
        params: dict[str, Any] | None = None,
        input_hash: str = "",
        output_hash: str = "",
        parent_ids: list[str] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Any: ...  # noqa: ANN401


class RateLimitConfig(BaseModel):
    """Rate-limiting configuration for a provider endpoint."""

    requests_per_minute: int = Field(default=60, gt=0)
    burst_size: int = Field(default=10, gt=0)
    retry_after: float = Field(default=5.0, gt=0)
    jitter_factor: float = Field(default=0.1, ge=0.0, le=1.0)


class ProviderConfig(BaseModel):
    """Connection configuration for an LLM provider endpoint."""

    api_key: SecretStr | None = None
    base_url: str = ""
    default_model: str = ""
    timeout: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    extra_headers: dict[str, str] = Field(default_factory=dict)
    rate_limit_config: RateLimitConfig = Field(default_factory=RateLimitConfig)
    provenance_tracker: Any | None = None


class HealthStatus:
    """Result of a provider health check with latency and error detail."""

    def __init__(self, ok: bool, latency_ms: float = 0.0, error: str = "") -> None:
        self.ok = ok
        self.latency_ms = latency_ms
        self.error = error


class ModelProvider(ABC):
    """Abstract base class for LLM providers with streaming, tool use, and health checks."""

    PROVIDER_NAME: str = "unknown"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig()

    @abstractmethod
    def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        """Stream a chat completion from the provider (implementation hook).

        Subclasses implement this as an async generator that yields Chunk
        objects.  The public ``stream_chat`` method wraps this with provenance
        recording.

        Args:
            messages: Conversation history.
            tools: Optional tool definitions for function calling.
            temperature: Override the default temperature.
            max_tokens: Override the default max tokens.
            provenance_parent_id: Optional provenance entry ID to link to.

        Yields:
            Chunk objects with incremental content deltas.
        """

    def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        """Stream a chat completion with automatic provenance recording.

        Records input provenance before streaming and output/error provenance
        after streaming completes.  Provenance is opt-in — only recorded when
        ``ProviderConfig.provenance_tracker`` is set.  Failures in provenance
        recording are logged and swallowed.
        """
        tracker = getattr(self._config, "provenance_tracker", None)

        # Record input provenance
        action_id: str | None = None
        if tracker is not None:
            try:
                input_hash = hashlib.sha256(
                    json.dumps(
                        [m.to_dict() for m in messages],
                        sort_keys=True,
                        default=str,
                    ).encode(),
                ).hexdigest()
                entry = tracker.track(
                    action_type="model_inference",
                    model_id=self._config.default_model,
                    params={"tools_provided": len(tools) if tools else 0},
                    input_hash=input_hash,
                    parent_ids=[provenance_parent_id] if provenance_parent_id else [],
                )
                action_id = getattr(entry, "action_id", None)
            except Exception:
                logger.warning("Failed to record input provenance", exc_info=True)

        # Wrapped async generator that records output/error provenance
        async def _gen() -> AsyncIterator[Chunk]:
            hash_ctx = hashlib.sha256() if tracker is not None else None
            error: Exception | None = None
            try:
                async for chunk in self._do_stream_chat(
                    messages,
                    tools,
                    temperature,
                    max_tokens,
                    provenance_parent_id=action_id,
                ):
                    if hash_ctx is not None and chunk.delta_content:
                        hash_ctx.update(chunk.delta_content.encode())
                    yield chunk
            except Exception as exc:
                error = exc
                raise
            finally:
                if tracker is not None and action_id is not None:
                    try:
                        if error is not None:
                            tracker.track(
                                action_type="model_inference_error",
                                model_id=self._config.default_model,
                                params={"error": str(error)},
                                parent_ids=[action_id],
                            )
                        else:
                            output_hash = hash_ctx.hexdigest() if hash_ctx else ""
                            tracker.track(
                                action_type="model_inference_result",
                                model_id=self._config.default_model,
                                output_hash=output_hash,
                                parent_ids=[action_id],
                            )
                    except Exception:
                        logger.warning("Failed to record output provenance", exc_info=True)

        return _gen()

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """List available models from the provider.

        Returns:
            List of ModelInfo objects describing available models.
        """

    def supports_tool_use(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False

    def supports_streaming(self) -> bool:
        return True

    def get_capabilities(self, model_id: str | None = None) -> ModelCapabilities:
        """Return capabilities for a specific model.

        Override in adapters that have per-model capability data.
        Default implementation uses the static ``supports_*`` flags.

        Args:
            model_id: Optional model identifier. Providers may use this
                for model-specific capability resolution. ``None`` means
                the provider's default model.

        Returns:
            ``ModelCapabilities`` for the given model.
        """
        _ = model_id
        return ModelCapabilities(
            tool_use=self.supports_tool_use(),
            vision=self.supports_vision(),
            streaming=self.supports_streaming(),
            function_calling=self.supports_tool_use(),
        )

    async def get_token_count(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def get_context_window(self) -> int:
        return 4096

    async def get_model_card(self) -> ModelCard:
        return ModelCard(provider=self.PROVIDER_NAME)

    async def health(self) -> HealthStatus:
        """Check provider connectivity by listing models.

        Returns:
            HealthStatus with ok flag, latency, and error detail on failure.
        """
        start = time.monotonic()
        try:
            await self.list_models()
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(ok=True, latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(ok=False, latency_ms=elapsed, error=str(exc))

    def _build_metrics(
        self,
        provider_name: str,
        model_name: str,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> ProviderMetrics:
        return ProviderMetrics(
            provider_name=provider_name,
            model_name=model_name,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
