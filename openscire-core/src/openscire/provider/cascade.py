# SPDX-License-Identifier: Apache-2.0

"""Fallback cascade provider — tries multiple model providers in sequence.

The ``CascadeProvider`` wraps an ordered list of ``(name, ModelProvider)`` pairs
and implements ``ModelProvider`` itself. On ``stream_chat``, it tries each
provider in order. If a provider fails with a recoverable error (connection
failure, timeout, rate limit), the cascade advances to the next provider.

Graceful degradation strips unsupported capabilities (vision, tool use) when
falling back to a less capable provider.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

import httpx

from openscire.constants import ErrorCode
from openscire.exceptions import ModelProviderError
from openscire.provider.base import HealthStatus, ModelProvider, ProviderConfig
from openscire.provider.capabilities import strip_unsupported
from openscire.provider.models import (
    ChatMessage,
    Chunk,
    FallbackInfo,
    ModelCard,
    ModelInfo,
)


class _ProvenanceTracker(Protocol):
    """Minimal protocol for a provenance tracker used by the fallback cascade."""

    def track(
        self,
        action_type: str,
        model_id: str,
        params: dict[str, Any] | None = None,
        **kwargs: object,
    ) -> Any: ...  # noqa: ANN401


_FALLBACK_TRIGGERS: set[ErrorCode] = {
    ErrorCode.MODEL_CONNECTION_FAILURE,
    ErrorCode.MODEL_RATE_LIMIT,
    ErrorCode.MODEL_UNSUPPORTED_CAPABILITY,
}


class CascadeConfig:
    """Configuration for the fallback cascade provider.

    Parameters:
        user_consent: Whether to await a consent callback before falling back.
        graceful_degradation: Strip unsupported capabilities (vision, tools)
            when falling back to a less capable provider.
        log_to_provenance: Whether to record fallback events to provenance.
        include_auth_fallback: Whether ``MODEL_AUTH_FAILURE`` (401) triggers
            a fallback. Off by default — a bad key won't be fixed by a
            different provider if it uses the same keychain.
        failure_exhausted_message: Template for the error raised when all
            providers are exhausted. ``{error}`` is replaced with the last
            error message.
    """

    def __init__(
        self,
        user_consent: bool = True,
        graceful_degradation: bool = True,
        log_to_provenance: bool = False,
        include_auth_fallback: bool = False,
        failure_exhausted_message: str = ("All cascade providers exhausted. Last error: {error}"),
    ) -> None:
        self.user_consent = user_consent
        self.graceful_degradation = graceful_degradation
        self.log_to_provenance = log_to_provenance
        self.include_auth_fallback = include_auth_fallback
        self.failure_exhausted_message = failure_exhausted_message


class CascadeProvider(ModelProvider):
    """Meta-provider that tries multiple providers in sequence until one succeeds.

    Each step in the cascade is a ``(name, ModelProvider)`` pair.  The name is
    used for disambiguation in ``list_models()`` output (prefixed with
    ``cascade:name``) and in ``FallbackInfo.attempted_provider``.

    Args:
        cascade: Ordered list of ``(name, provider)`` tuples.
        config: Base ``ProviderConfig`` for the cascade itself (used for
            ``default_model`` metadata only).
        cascade_config: Fine-grained fallback behaviour.
        consent_callback: Async callback invoked before each fallback step
            when ``user_consent`` is True. Receives the ``FallbackInfo`` and
            returns ``True`` to allow the fallback or ``False`` to re-raise
            the error.
        provenance_tracker: Optional tracker for recording fallback events.
            Must expose a ``track(action_type, model_id, params, metadata)``
            method.
    """

    PROVIDER_NAME = "cascade"

    def __init__(
        self,
        cascade: list[tuple[str, ModelProvider]],
        config: ProviderConfig | None = None,
        cascade_config: CascadeConfig | None = None,
        consent_callback: Callable[[FallbackInfo], Awaitable[bool]] | None = None,
        provenance_tracker: _ProvenanceTracker | None = None,
    ) -> None:
        super().__init__(config)
        if not cascade:
            raise ValueError("Cascade must contain at least one provider")
        self._cascade = cascade
        self._cascade_config = cascade_config or CascadeConfig()
        self._consent_callback = consent_callback
        self._provenance_tracker = provenance_tracker

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        """Try each provider in the cascade; yield chunks from the first success.

        Yields ``Chunk`` objects with ``fallback_info`` set when switching
        providers.  If all providers fail, raises ``ModelProviderError``.
        """
        last_error: Exception | None = None

        for step_idx, (_name, provider) in enumerate(self._cascade):
            chunks_yielded = False
            try:
                p_messages, p_tools = self._preprocess(
                    messages,
                    tools,
                    provider,
                )
                async for chunk in provider.stream_chat(
                    p_messages,
                    p_tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    provenance_parent_id=provenance_parent_id,
                ):
                    chunks_yielded = True
                    yield chunk
                return
            except Exception as exc:
                last_error = exc
                if chunks_yielded:
                    raise
                is_last = step_idx >= len(self._cascade) - 1
                if is_last:
                    continue
                if not self._should_fallback(exc, step_idx):
                    raise

                info = self._build_fallback_info(step_idx, exc)
                yield Chunk(fallback_info=info)

                if self._cascade_config.user_consent and self._consent_callback:
                    allowed = await self._consent_callback(info)
                    if not allowed:
                        raise exc

                if self._cascade_config.log_to_provenance and self._provenance_tracker is not None:
                    self._log_fallback(info, provenance_parent_id)

        msg = self._cascade_config.failure_exhausted_message.format(
            error=str(last_error),
        )
        raise ModelProviderError(
            message=msg,
            source="provider.cascade",
            error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
        )

    async def list_models(self) -> list[ModelInfo]:
        """Aggregate ``ModelInfo`` from every child provider.

        Model IDs are prefixed with ``{name}/`` for disambiguation.
        """
        result: list[ModelInfo] = []
        for name, provider in self._cascade:
            try:
                child_models = await provider.list_models()
            except Exception:
                continue
            for m in child_models:
                result.append(
                    ModelInfo(
                        id=f"{name}/{m.id}",
                        name=f"{name}/{m.name}",
                        provider=f"cascade:{name}",
                        context_window=m.context_window,
                        capabilities=m.capabilities,
                        quantization=m.quantization,
                    )
                )
        return result

    def supports_tool_use(self) -> bool:
        return any(p.supports_tool_use() for _, p in self._cascade)

    def supports_vision(self) -> bool:
        return any(p.supports_vision() for _, p in self._cascade)

    def supports_streaming(self) -> bool:
        return any(p.supports_streaming() for _, p in self._cascade)

    async def get_token_count(self, text: str) -> int:
        return await self._cascade[0][1].get_token_count(text)

    async def get_context_window(self) -> int:
        windows: list[int] = []
        for _, p in self._cascade:
            windows.append(await p.get_context_window())
        return max(windows, default=4096)

    async def get_model_card(self) -> ModelCard:
        return ModelCard(
            provider=self.PROVIDER_NAME,
            intended_use=(
                "Multi-provider fallback cascade for resilient inference. "
                "Automatically tries backup providers on failure."
            ),
            limitations=[
                "Different providers may produce inconsistent output",
                "Fallback adds latency proportional to the number of failed attempts",
                "Capability differences between providers may affect output quality",
            ],
        )

    async def health(self) -> HealthStatus:
        start = time.monotonic()
        for _name, provider in self._cascade:
            status = await provider.health()
            if status.ok:
                elapsed = (time.monotonic() - start) * 1000
                return HealthStatus(ok=True, latency_ms=elapsed)
        elapsed = (time.monotonic() - start) * 1000
        return HealthStatus(
            ok=False,
            latency_ms=elapsed,
            error="No provider in cascade is healthy",
        )

    def _should_fallback(self, exc: Exception, step_idx: int) -> bool:
        if step_idx >= len(self._cascade) - 1:
            return False
        if isinstance(exc, ModelProviderError):
            error_code = ErrorCode(exc.error_code) if exc.error_code else None
            if error_code in _FALLBACK_TRIGGERS:
                return True
            return bool(
                self._cascade_config.include_auth_fallback
                and error_code == ErrorCode.MODEL_AUTH_FAILURE
            )
        return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, TimeoutError))

    def _preprocess(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None,
        provider: ModelProvider,
    ) -> tuple[list[ChatMessage], list[dict[str, Any]] | None]:
        if not self._cascade_config.graceful_degradation:
            return messages, tools

        caps = provider.get_capabilities()
        return strip_unsupported(messages, tools, caps)

    def _build_fallback_info(self, step_idx: int, exc: Exception) -> FallbackInfo:
        name = self._cascade[step_idx][0]
        provider = self._cascade[step_idx][1]
        model = provider._config.default_model if hasattr(provider, "_config") else ""
        error_code = ""
        if isinstance(exc, ModelProviderError):
            error_code = exc.error_code or ""
        return FallbackInfo(
            step_index=step_idx,
            total_steps=len(self._cascade),
            attempted_provider=name,
            attempted_model=model,
            error_message=str(exc),
            error_code=error_code,
            latency_ms=0.0,
        )

    def _log_fallback(self, info: FallbackInfo, provenance_parent_id: str | None = None) -> None:
        if self._provenance_tracker is None:
            return
        parent_ids: list[str] = []
        if provenance_parent_id is not None:
            parent_ids.append(provenance_parent_id)
        with contextlib.suppress(Exception):
            self._provenance_tracker.track(
                action_type="model_fallback",
                model_id=info.attempted_model,
                params={
                    "step_index": info.step_index,
                    "total_steps": info.total_steps,
                    "attempted_provider": info.attempted_provider,
                    "error_code": info.error_code,
                    "error_message": info.error_message,
                },
                parent_ids=parent_ids or None,
            )
