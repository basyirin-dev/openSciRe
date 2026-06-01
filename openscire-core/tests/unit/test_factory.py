# SPDX-License-Identifier: Apache-2.0

"""Tests for provider factory (select_provider)."""

from openscire.provider import (
    AnthropicProvider,
    GeminiProvider,
    LiteLLMProvider,
    OpenAICompatibleProvider,
    ProviderConfig,
    select_provider,
)


class _MockFactory:
    """Minimal struct for mimicking BYOKProfile.to_provider_config."""

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig(default_model="gpt-4o")

    def to_provider_config(self) -> ProviderConfig:
        return self._config


# ---------------------------------------------------------------------------
# TestSelectProviderExplicit
# ---------------------------------------------------------------------------


class TestSelectProviderExplicit:
    def test_gpt_prefix_returns_openai(self) -> None:
        provider = select_provider("gpt-4o")
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_claude_prefix_returns_anthropic(self) -> None:
        provider = select_provider("claude-3-5-sonnet")
        assert isinstance(provider, AnthropicProvider)

    def test_gemini_prefix_returns_gemini(self) -> None:
        provider = select_provider("gemini-2.0-flash")
        assert isinstance(provider, GeminiProvider)

    def test_unknown_prefix_returns_litellm(self) -> None:
        provider = select_provider("some-custom-model")
        assert isinstance(provider, LiteLLMProvider)

    def test_o1_prefix_returns_openai(self) -> None:
        provider = select_provider("o1-mini")
        assert isinstance(provider, OpenAICompatibleProvider)


# ---------------------------------------------------------------------------
# TestSelectProviderCaseInsensitive
# ---------------------------------------------------------------------------


class TestSelectProviderCaseInsensitive:
    def test_gpt_uppercase(self) -> None:
        provider = select_provider("GPT-4o")
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_claude_uppercase(self) -> None:
        provider = select_provider("Claude-3-5-Sonnet")
        assert isinstance(provider, AnthropicProvider)

    def test_mixed_case_fallback(self) -> None:
        provider = select_provider("Custom-Model")
        assert isinstance(provider, LiteLLMProvider)


# ---------------------------------------------------------------------------
# TestSelectProviderForce
# ---------------------------------------------------------------------------


class TestSelectProviderForce:
    def test_force_openai(self) -> None:
        provider = select_provider("claude-3-haiku", force="openai")
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_force_anthropic(self) -> None:
        provider = select_provider("gpt-4o", force="anthropic")
        assert isinstance(provider, AnthropicProvider)

    def test_force_gemini(self) -> None:
        provider = select_provider("gpt-4o", force="gemini")
        assert isinstance(provider, GeminiProvider)

    def test_force_litellm(self) -> None:
        provider = select_provider("gpt-4o", force="litellm")
        assert isinstance(provider, LiteLLMProvider)


# ---------------------------------------------------------------------------
# TestSelectProviderWithBYOK
# ---------------------------------------------------------------------------


class TestSelectProviderWithBYOK:
    def test_byok_profile_injects_config(self) -> None:
        cfg = ProviderConfig(default_model="claude-3-opus", base_url="https://custom.anthropic.com")
        profile = _MockFactory(config=cfg)
        provider = select_provider("claude-3-opus", byok_profile=profile)
        assert isinstance(provider, AnthropicProvider)
        assert provider._config.base_url == "https://custom.anthropic.com"

    def test_byok_profile_model_mismatch(self) -> None:
        cfg = ProviderConfig(default_model="gpt-4o")
        profile = _MockFactory(config=cfg)
        provider = select_provider("gpt-4o", byok_profile=profile)
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider._config.default_model == "gpt-4o"
