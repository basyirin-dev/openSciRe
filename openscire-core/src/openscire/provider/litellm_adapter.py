# SPDX-License-Identifier: Apache-2.0

"""LiteLLM-based model providers.

Provides two classes that wrap the LiteLLM Python SDK:

* ``LiteLLMProvider`` — calls ``litellm.acompletion()`` directly (single model,
  no router). Use this for ad-hoc access to any provider LiteLLM supports.
* ``LiteLLMRouterProvider`` — wraps ``litellm.Router`` for load balancing,
  rate limiting, cooldown, and model fallback lists.

Both classes share ``_LiteLLMBase`` for LiteLLM-specific error mapping, message
conversion, cost extraction, and model-listing.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openscire.constants import ErrorCode
from openscire.exceptions import ModelProviderError
from openscire.provider.base import HealthStatus, ModelProvider, ProviderConfig
from openscire.provider.capabilities import _SUPPORTED_MODELS
from openscire.provider.models import (
    ChatMessage,
    Chunk,
    FallbackInfo,
    FinishReason,
    ModelCapabilities,
    ModelCard,
    ModelInfo,
    ProviderMetrics,
)

# ---------------------------------------------------------------------------
# Optional dependency guard
# ---------------------------------------------------------------------------

try:
    import litellm
except ImportError:  # pragma: no cover
    litellm = None  # type: ignore[assignment]


def _require_litellm() -> None:
    """Raise a clear ``ImportError`` if ``litellm`` is not installed."""
    if litellm is None:
        msg = (
            "The LiteLLM provider requires the 'litellm' package."
            " Install it with:  pip install openscire-core[router]"
        )
        raise ImportError(msg)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class LiteLLMRouterConfig:
    """Fine-grained configuration for ``LiteLLMRouterProvider``.

    Parameters:
        num_retries: Number of tenacity retries per request.
        timeout: Request timeout in seconds.
        routing_strategy: Load-balancing strategy for the Router.
            One of ``simple-shuffle``, ``least-busy``,
            ``usage-based-routing``, ``latency-based-routing``,
            ``cost-based-routing``.
        allowed_fails: Number of consecutive failures before a deployment is
            cooled down.
        cooldown_time: Cooldown period in seconds for a failed deployment.
        enable_weighted_failover: Whether to retry within the same model
            group before escalating to cross-group fallbacks.
        context_window_fallbacks: Mapping of model names to fallback model IDs
            for context-window overflow.
    """

    num_retries: int = 3
    timeout: float = 30.0
    routing_strategy: str = "simple-shuffle"
    allowed_fails: int = 3
    cooldown_time: float = 30.0
    enable_weighted_failover: bool = False
    context_window_fallbacks: dict[str, list[str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Capability resolution (module-level, shared by mixin and static helpers)
# ---------------------------------------------------------------------------

_PATTERN_CAPABILITIES: list[tuple[str, ModelCapabilities]] = [
    (
        "gpt-4o",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    ("gpt-4", ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True)),
    (
        "gpt-3.5",
        ModelCapabilities(tool_use=True, vision=False, streaming=True, function_calling=True),
    ),
    ("o1", ModelCapabilities(tool_use=True, vision=True, streaming=False, function_calling=True)),
    ("o3", ModelCapabilities(tool_use=True, vision=True, streaming=False, function_calling=True)),
    ("o4", ModelCapabilities(tool_use=True, vision=True, streaming=False, function_calling=True)),
    (
        "claude-sonnet-4",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    (
        "claude-opus-4",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    (
        "claude-3-5",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    (
        "claude-3",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    (
        "claude-haiku",
        ModelCapabilities(tool_use=True, vision=False, streaming=True, function_calling=True),
    ),
    (
        "gemini-2.5",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    (
        "gemini-2.0",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    (
        "gemini-pro",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    (
        "gemini-flash",
        ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True),
    ),
    (
        "llama",
        ModelCapabilities(tool_use=True, vision=False, streaming=True, function_calling=False),
    ),
    (
        "mistral",
        ModelCapabilities(tool_use=True, vision=False, streaming=True, function_calling=True),
    ),
    (
        "mixtral",
        ModelCapabilities(tool_use=True, vision=False, streaming=True, function_calling=True),
    ),
    (
        "deepseek",
        ModelCapabilities(tool_use=True, vision=False, streaming=True, function_calling=False),
    ),
    ("qwen", ModelCapabilities(tool_use=True, vision=True, streaming=True, function_calling=True)),
    (
        "command-r",
        ModelCapabilities(tool_use=True, vision=False, streaming=True, function_calling=True),
    ),
    (
        "dbrx",
        ModelCapabilities(tool_use=False, vision=False, streaming=True, function_calling=False),
    ),
    (
        "phi",
        ModelCapabilities(tool_use=False, vision=False, streaming=True, function_calling=False),
    ),
    (
        "tinyllama",
        ModelCapabilities(tool_use=False, vision=False, streaming=True, function_calling=False),
    ),
]


def _capabilities_for_model(model_id: str) -> ModelCapabilities:
    """Resolve capabilities for *model_id* using the heuristic table."""
    if not model_id:
        return ModelCapabilities()
    if model_id in _SUPPORTED_MODELS:
        return _SUPPORTED_MODELS[model_id]
    lower = model_id.lower()
    for prefix, caps in _PATTERN_CAPABILITIES:
        if lower.startswith(prefix):
            return caps
    return ModelCapabilities()


def _build_model_info_from_cost(
    model_id: str,
    provider: str = "litellm",
) -> ModelInfo | None:
    """Build a ``ModelInfo`` from ``litellm.model_cost`` (if available)."""
    if litellm is None:
        return None
    entry = litellm.model_cost.get(model_id)
    if not entry:
        return None
    context_window = entry.get("max_tokens", 4096)
    input_cost = float(entry.get("input_cost_per_token", 0.0))
    output_cost = float(entry.get("output_cost_per_token", 0.0))
    caps = _SUPPORTED_MODELS.get(model_id.lower(), _capabilities_for_model(model_id))
    return ModelInfo(
        id=model_id,
        name=entry.get("litellm_provider", "") + "/" + model_id,
        provider=provider,
        context_window=context_window,
        capabilities=caps,
        pricing_per_1k_input=input_cost * 1000,
        pricing_per_1k_output=output_cost * 1000,
    )


# ---------------------------------------------------------------------------
# Shared LiteLLM mixin
# ---------------------------------------------------------------------------


class _LiteLLMBase:
    """Mixin with shared LiteLLM utilities.

    Provides error mapping, message conversion, cost extraction, and model
    listing helpers. **Must be used alongside ``ModelProvider``**.

    Subclasses must have ``self._config`` (``ProviderConfig``) and set
    ``PROVIDER_NAME``.
    """

    PROVIDER_NAME: str = "litellm_base"
    _config: ProviderConfig

    def _map_litellm_error(self, exc: Exception) -> ModelProviderError:
        """Map a ``litellm`` exception to a ``ModelProviderError``."""
        if litellm is None:
            return ModelProviderError(
                message=f"LiteLLM is not installed: {exc}",
                source="provider.litellm",
                error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
            )

        if isinstance(exc, litellm.AuthenticationError):
            return ModelProviderError(
                message=str(exc),
                source="provider.litellm",
                error_code=ErrorCode.MODEL_AUTH_FAILURE,
            )
        if isinstance(exc, litellm.RateLimitError):
            return ModelProviderError(
                message=str(exc),
                source="provider.litellm",
                error_code=ErrorCode.MODEL_RATE_LIMIT,
            )
        if isinstance(exc, litellm.ContextWindowExceededError):
            return ModelProviderError(
                message=str(exc),
                source="provider.litellm",
                error_code=ErrorCode.MODEL_UNSUPPORTED_CAPABILITY,
            )
        if isinstance(exc, (litellm.APIConnectionError, litellm.ServiceUnavailableError)):
            return ModelProviderError(
                message=str(exc),
                source="provider.litellm",
                error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
            )
        if isinstance(exc, litellm.BadRequestError):
            return ModelProviderError(
                message=str(exc),
                source="provider.litellm",
                error_code=ErrorCode.MODEL_UNSUPPORTED_CAPABILITY,
            )
        if isinstance(exc, litellm.ContentPolicyViolationError):
            return ModelProviderError(
                message=str(exc),
                source="provider.litellm",
                error_code=ErrorCode.MODEL_UNSUPPORTED_CAPABILITY,
            )

        return ModelProviderError(
            message=f"{type(exc).__name__}({type(exc).__module__}): {exc}",
            source="provider.litellm",
            error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
        )

    @staticmethod
    def _finish_reason_from_litellm(reason: str | None) -> FinishReason | None:
        if reason is None or reason == "":
            return None
        mapping = {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
            "tool_calls": FinishReason.TOOL_CALLS,
            "content_filter": FinishReason.CONTENT_FILTER,
            "function_call": FinishReason.TOOL_CALLS,
        }
        return mapping.get(reason.lower(), FinishReason.STOP)

    @staticmethod
    def _convert_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}
            if isinstance(msg.content, list):
                parts: list[dict[str, Any]] = []
                for part in msg.content:
                    if isinstance(part, dict) or hasattr(part, "type"):
                        p = part if isinstance(part, dict) else part.__dict__
                        p_type = p.get("type", "text")
                        if p_type == "image_url":
                            parts.append({"type": "image_url", "image_url": p.get("image_url", {})})
                        else:
                            parts.append({"type": "text", "text": p.get("text", "")})
                    else:
                        parts.append({"type": "text", "text": str(part)})
                entry["content"] = parts
            elif msg.content:
                entry["content"] = msg.content
            else:
                entry["content"] = ""
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            out.append(entry)
        return out

    @staticmethod
    def _cost_from_response(response: Any) -> float:  # noqa: ANN401
        try:
            return float(getattr(response, "_hidden_params", {}).get("response_cost", 0.0))
        except (TypeError, ValueError):
            return 0.0

    async def get_token_count(self, text: str) -> int:
        _require_litellm()
        try:
            return litellm.token_counter(model=self._config.default_model, text=text)
        except Exception:
            return max(1, len(text) // 4)

    async def get_context_window(self) -> int:
        model_id = self._config.default_model
        if litellm is not None and model_id:
            try:
                return litellm.get_max_tokens(model=model_id) or 4096
            except Exception:
                pass
        return 4096

    async def get_model_card(self) -> ModelCard:
        _require_litellm()
        model_id = self._config.default_model
        description = ""
        if model_id and model_id in litellm.model_cost:
            entry = litellm.model_cost[model_id]
            description = entry.get("litellm_provider", "LiteLLM")
        return ModelCard(
            provider=self.PROVIDER_NAME,
            training_data_summary=(
                "LiteLLM is a unified SDK for 100+ LLM providers. "
                "Model-specific training data details vary by provider."
            ),
            intended_use=f"Unified access to {description} via the LiteLLM SDK.",
            limitations=[
                "Cost estimates are from LiteLLM's community-maintained model_cost dict",
                "Enterprise or negotiated pricing is not reflected",
                "Provider availability depends on upstream API health",
                "Not all models support all features (vision, tool calls)",
            ],
            safety_ratings={
                "cost_source": "litellm.model_cost (community maintained, best-effort)",
                "cost_currency": "USD",
            },
        )


# ---------------------------------------------------------------------------
# Tool-call delta parser
# ---------------------------------------------------------------------------


def _parse_delta_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:  # noqa: ANN401
    result: list[dict[str, Any]] = []
    for tc in tool_calls:
        entry: dict[str, Any] = {
            "id": tc.id,
            "type": tc.type,
            "function": {"name": "", "arguments": ""},
        }
        if hasattr(tc, "function") and tc.function:
            entry["function"]["name"] = getattr(tc.function, "name", "") or ""
            entry["function"]["arguments"] = getattr(tc.function, "arguments", "") or ""
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# LiteLLMProvider — direct acompletion wrapper (no router)
# ---------------------------------------------------------------------------


class LiteLLMProvider(_LiteLLMBase, ModelProvider):
    """Provider adapter calling ``litellm.acompletion()`` directly.

    This is the universal fallback for any model / provider that LiteLLM
    supports but that does not have a dedicated explicit adapter in openSciRe.

    Requires the ``litellm`` package. Install with
    ``pip install openscire-core[router]``.
    """

    PROVIDER_NAME = "litellm"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config)
        if not self._config.default_model:
            raise ValueError("LiteLLMProvider requires a non-empty default_model in ProviderConfig")

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        _ = provenance_parent_id
        _require_litellm()

        payload = self._convert_messages(messages)
        start = time.monotonic()

        kwargs: dict[str, Any] = {
            "model": self._config.default_model,
            "messages": payload,
            "stream": True,
            "stream_options": {"include_usage": True},
            "num_retries": self._config.max_retries,
        }
        if tools:
            kwargs["tools"] = tools
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            response = await litellm.acompletion(**kwargs)
            final_cost = 0.0
            prompt_tokens = 0
            completion_tokens = 0

            async for chunk in response:
                if chunk is None:
                    continue

                choices = chunk.choices if hasattr(chunk, "choices") else []
                choice = choices[0] if choices else None
                if choice is None:
                    continue

                delta = choice.delta if hasattr(choice, "delta") else None

                chunk_out = Chunk()

                if delta:
                    chunk_out.delta_content = getattr(delta, "content", "") or ""
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        chunk_out.tool_calls = _parse_delta_tool_calls(delta.tool_calls)

                finish_reason = getattr(choice, "finish_reason", None)
                if finish_reason:
                    chunk_out.finish_reason = self._finish_reason_from_litellm(finish_reason)

                if hasattr(chunk, "usage") and chunk.usage:
                    usage = chunk.usage
                    prompt_tokens = getattr(usage, "prompt_tokens", prompt_tokens)
                    completion_tokens = getattr(usage, "completion_tokens", completion_tokens)
                    final_cost = self._cost_from_response(chunk)

                yield chunk_out

            elapsed = (time.monotonic() - start) * 1000
            yield Chunk(
                provider_metrics=ProviderMetrics(
                    provider_name=self.PROVIDER_NAME,
                    model_name=self._config.default_model,
                    latency_ms=elapsed,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    cost=final_cost,
                )
            )

        except Exception as exc:
            raise self._map_litellm_error(exc) from exc

    async def list_models(self) -> list[ModelInfo]:
        _require_litellm()
        model_id = self._config.default_model

        if model_id and model_id in litellm.model_cost:
            info = _build_model_info_from_cost(model_id)
            if info:
                return [info]

        if model_id:
            return [
                ModelInfo(
                    id=model_id,
                    name=model_id,
                    provider=self.PROVIDER_NAME,
                    context_window=4096,
                )
            ]

        return [
            ModelInfo(id="gpt-4o-mini", name="gpt-4o-mini", provider=self.PROVIDER_NAME),
        ]

    def supports_tool_use(self) -> bool:
        return _capabilities_for_model(self._config.default_model).tool_use

    def supports_vision(self) -> bool:
        return _capabilities_for_model(self._config.default_model).vision

    def get_capabilities(self, model_id: str | None = None) -> ModelCapabilities:
        return _capabilities_for_model(
            model_id or self._config.default_model or "",
        )

    async def health(self) -> HealthStatus:
        _require_litellm()
        model_id = self._config.default_model
        start = time.monotonic()
        try:
            if model_id and model_id in litellm.model_cost:
                info = litellm.model_cost[model_id]
                _ = info.get("max_tokens", 4096)
            else:
                fallback_info = litellm.model_cost.get("gpt-4o-mini", {})
                _ = fallback_info.get("max_tokens", 4096)
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(ok=True, latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(ok=False, latency_ms=elapsed, error=str(exc))


# ---------------------------------------------------------------------------
# LiteLLMRouterProvider — wraps litellm.Router
# ---------------------------------------------------------------------------


class LiteLLMRouterProvider(_LiteLLMBase, ModelProvider):
    """Provider adapter wrapping ``litellm.Router`` for load balancing and fallback.

    Uses LiteLLM's built-in Router to manage multiple deployments, rate
    limiting, cooldown, and model fallback lists.

    Args:
        model_list: List of deployment dicts in LiteLLM's format
            (``model_name`` + ``litellm_params``).
        config: Base ``ProviderConfig`` used for ``default_model`` metadata.
        router_config: Fine-grained routing and fallback configuration.
        fallbacks: Optional ``[{model_name: [fallback_model, ...]}]`` list for
            cross-model fallback (general errors).

    Example:
        .. code-block:: python

            provider = LiteLLMRouterProvider(
                model_list=[
                    {"model_name": "gpt-4o", "litellm_params": {"model": "openai/gpt-4o"}},
                ],
                fallbacks=[{"gpt-4o": ["claude-3-5-sonnet"]}],
            )
    """

    PROVIDER_NAME = "litellm_router"

    def __init__(
        self,
        model_list: list[dict[str, Any]],
        config: ProviderConfig | None = None,
        router_config: LiteLLMRouterConfig | None = None,
        fallbacks: list[dict[str, list[str]]] | None = None,
    ) -> None:
        super().__init__(config)
        if not model_list:
            raise ValueError("LiteLLMRouterProvider requires a non-empty model_list")
        _require_litellm()

        self._router_config = router_config or LiteLLMRouterConfig()
        self._model_list = model_list

        kwargs: dict[str, Any] = {
            "model_list": model_list,
            "num_retries": self._router_config.num_retries,
            "timeout": self._router_config.timeout,
            "routing_strategy": self._router_config.routing_strategy,
            "allowed_fails": self._router_config.allowed_fails,
            "cooldown_time": self._router_config.cooldown_time,
        }
        if self._router_config.enable_weighted_failover:
            kwargs["enable_weighted_failover"] = True
        if fallbacks:
            kwargs["fallbacks"] = fallbacks
        ctx = self._router_config.context_window_fallbacks
        if ctx:
            kwargs["context_window_fallback_dict"] = ctx

        self._last_fallback_info: FallbackInfo | None = None
        self._router = litellm.Router(**kwargs)

        litellm.success_callback = [self._on_litellm_success]

    def _on_litellm_success(
        self,
        kwargs: dict[str, Any],
        completion_response: Any,  # noqa: ANN401, ARG002
        start_time: float,  # noqa: ARG002
        end_time: float,  # noqa: ARG002
    ) -> None:
        """Capture fallback events triggered by the Router."""
        orig_model = kwargs.get("original_model_group")
        actual_model = kwargs.get("model_group")
        if orig_model and actual_model and orig_model != actual_model:
            step = kwargs.get("num_fallbacks", 0)
            err = kwargs.get("exception", "")
            self._last_fallback_info = FallbackInfo(
                step_index=step,
                total_steps=step + 1,
                attempted_provider=self.PROVIDER_NAME,
                attempted_model=str(actual_model),
                error_message=str(err) if err else "fallback triggered",
                error_code="",
            )

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        _ = provenance_parent_id

        payload = self._convert_messages(messages)
        start = time.monotonic()

        kwargs: dict[str, Any] = {
            "messages": payload,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if self._config.default_model:
            kwargs["model"] = self._config.default_model
        if tools:
            kwargs["tools"] = tools
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            if self._last_fallback_info is not None:
                yield Chunk(fallback_info=self._last_fallback_info)
                self._last_fallback_info = None

            response = await self._router.acompletion(**kwargs)
            final_cost = 0.0
            prompt_tokens = 0
            completion_tokens = 0

            async for chunk in response:
                if chunk is None:
                    continue

                choices = chunk.choices if hasattr(chunk, "choices") else []
                choice = choices[0] if choices else None
                if choice is None:
                    continue

                delta = choice.delta if hasattr(choice, "delta") else None

                chunk_out = Chunk()

                if delta:
                    chunk_out.delta_content = getattr(delta, "content", "") or ""
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        chunk_out.tool_calls = _parse_delta_tool_calls(delta.tool_calls)

                finish_reason = getattr(choice, "finish_reason", None)
                if finish_reason:
                    chunk_out.finish_reason = self._finish_reason_from_litellm(finish_reason)

                if hasattr(chunk, "usage") and chunk.usage:
                    usage = chunk.usage
                    prompt_tokens = getattr(usage, "prompt_tokens", prompt_tokens)
                    completion_tokens = getattr(usage, "completion_tokens", completion_tokens)
                    final_cost = self._cost_from_response(chunk)

                yield chunk_out

            elapsed = (time.monotonic() - start) * 1000
            yield Chunk(
                provider_metrics=ProviderMetrics(
                    provider_name=self.PROVIDER_NAME,
                    model_name=self._config.default_model
                    or self._model_list[0].get("model_name", ""),
                    latency_ms=elapsed,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    cost=final_cost,
                )
            )

        except Exception as exc:
            raise self._map_litellm_error(exc) from exc

    async def list_models(self) -> list[ModelInfo]:
        _require_litellm()
        model_names: list[str] = []
        with contextlib.suppress(Exception):
            model_names = self._router.get_model_names()

        result: list[ModelInfo] = []
        for name in model_names:
            info = _build_model_info_from_cost(name, provider=self.PROVIDER_NAME)
            if info:
                result.append(info)
            else:
                result.append(
                    ModelInfo(
                        id=name,
                        name=name,
                        provider=self.PROVIDER_NAME,
                    )
                )
        return result

    def supports_tool_use(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        model_id = self._config.default_model
        if model_id:
            return _capabilities_for_model(model_id).vision
        return True

    async def health(self) -> HealthStatus:
        start = time.monotonic()
        try:
            names = await self.list_models()
            elapsed = (time.monotonic() - start) * 1000
            if names:
                return HealthStatus(ok=True, latency_ms=elapsed)
            return HealthStatus(
                ok=False,
                latency_ms=elapsed,
                error="Router returned no models",
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(ok=False, latency_ms=elapsed, error=str(exc))

    @classmethod
    def from_litellm_yaml(
        cls,
        yaml_path: str,
        config: ProviderConfig | None = None,
        router_config: LiteLLMRouterConfig | None = None,
    ) -> LiteLLMRouterProvider:
        """Parse a LiteLLM ``config.yaml`` and instantiate a ``LiteLLMRouterProvider``.

        Args:
            yaml_path: Path to a LiteLLM YAML configuration file.
            config: Optional base ``ProviderConfig``.
            router_config: Optional ``LiteLLMRouterConfig`` overrides.

        Returns:
            A configured ``LiteLLMRouterProvider``.
        """
        import yaml

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        model_list = data.get("model_list", [])
        fallbacks: list[dict[str, list[str]]] = data.get("fallbacks", [])
        litellm_settings = data.get("litellm_settings", {})

        rc = router_config or LiteLLMRouterConfig()
        if "num_retries" in litellm_settings:
            rc.num_retries = int(litellm_settings["num_retries"])
        if "request_timeout" in litellm_settings:
            rc.timeout = float(litellm_settings["request_timeout"])
        if "allowed_fails" in litellm_settings:
            rc.allowed_fails = int(litellm_settings["allowed_fails"])
        if "cooldown_time" in litellm_settings:
            rc.cooldown_time = float(litellm_settings["cooldown_time"])

        ctx_fallbacks: dict[str, list[str]] = {}
        raw_fb = data.get(
            "context_window_fallbacks",
            litellm_settings.get("context_window_fallback_dict"),
        )
        if raw_fb:
            ctx_fallbacks = raw_fb
        rc.context_window_fallbacks = ctx_fallbacks

        return cls(
            model_list=model_list,
            config=config,
            router_config=rc,
            fallbacks=fallbacks if fallbacks else None,
        )
