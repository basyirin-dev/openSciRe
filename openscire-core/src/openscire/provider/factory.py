# SPDX-License-Identifier: Apache-2.0

"""Provider factory — automatically select the best ``ModelProvider`` for a
model name.

Usage:
    .. code-block:: python

        from openscire.provider.factory import select_provider
        from openscire.config.byok import BYOKProfile

        provider = select_provider("gpt-4o")
        # -> OpenAICompatibleProvider

        provider = select_provider("ollama/llama3.1")
        # -> LiteLLMProvider (via LiteLLM's ollama_chat prefix)

        profile = BYOKProfile(api_key="sk-...", provider_type="openai_compatible")
        provider = select_provider("claude-3-5-sonnet", byok_profile=profile)
        # -> AnthropicProvider, with API key from the profile
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openscire.config.byok import BYOKProfile

from openscire.provider.anthropic_adapter import AnthropicProvider
from openscire.provider.base import ModelProvider, ProviderConfig
from openscire.provider.gemini_adapter import GeminiProvider
from openscire.provider.litellm_adapter import LiteLLMProvider
from openscire.provider.openai_adapter import OpenAICompatibleProvider

# ---------------------------------------------------------------------------
# Explicit-adapter model prefixes
# ---------------------------------------------------------------------------

_OPENAI_PREFIXES = ("gpt-", "gpt-4", "gpt-3.5", "o1", "o3", "o4-", "text-embedding-")
_ANTHROPIC_PREFIXES = ("claude-",)
_GEMINI_PREFIXES = ("gemini-",)


def select_provider(
    model: str,
    byok_profile: BYOKProfile | None = None,
    force: str | None = None,
) -> ModelProvider:
    """Select the best ``ModelProvider`` for a model name.

    Selection order:
    1. If *force* is set, use that adapter directly.
    2. If the model name matches known prefixes, return the corresponding
       explicit adapter.
    3. Otherwise, return ``LiteLLMProvider`` (the universal fallback).

    Args:
        model: Model identifier (e.g. ``"gpt-4o"``, ``"claude-3-5-sonnet"``,
            ``"gemini-2.5-pro"``, ``"ollama/llama3.1"``).
        byok_profile: Optional ``BYOKProfile`` containing API key, base URL,
            and custom headers.
        force: Force a specific adapter type. Supported values:
            ``"openai"``, ``"anthropic"``, ``"gemini"``, ``"litellm"``.

    Returns:
        A ``ModelProvider`` instance configured for the given model.

    Raises:
        ValueError: If *force* is set to an unknown adapter type.
    """
    config = _build_config(model, byok_profile)

    if force is not None:
        return _force_adapter(force, config, model)

    lower = model.lower()

    if lower.startswith(_OPENAI_PREFIXES):
        return OpenAICompatibleProvider(config=config)

    if lower.startswith(_ANTHROPIC_PREFIXES):
        return AnthropicProvider(config=config)

    if lower.startswith(_GEMINI_PREFIXES):
        return GeminiProvider(config=config)

    return LiteLLMProvider(config=config)


def _build_config(model: str, byok_profile: object | None = None) -> ProviderConfig:
    """Build a ``ProviderConfig`` from optional BYOK profile."""
    if byok_profile is not None:
        profile_config = byok_profile.to_provider_config()
        profile_config.default_model = model
        return profile_config

    return ProviderConfig(default_model=model)


def _force_adapter(force: str, config: ProviderConfig, _model: str) -> ModelProvider:
    """Return an adapter based on explicit *force* parameter."""
    lower = force.lower()

    if lower == "openai":
        return OpenAICompatibleProvider(config=config)
    if lower == "anthropic":
        return AnthropicProvider(config=config)
    if lower == "gemini":
        return GeminiProvider(config=config)
    if lower == "litellm":
        return LiteLLMProvider(config=config)

    valid = {"openai", "anthropic", "gemini", "litellm"}
    raise ValueError(f"Unknown adapter type: '{force}'. Valid options: {', '.join(sorted(valid))}")
