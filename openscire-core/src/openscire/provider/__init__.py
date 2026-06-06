# SPDX-License-Identifier: Apache-2.0

"""Provider abstraction layer for openSciRe.

Defines the ModelProvider interface, provider-agnostic data models, and
concrete adapters (e.g., OpenAI-compatible API) for model inference.
"""

from openscire.provider.anthropic_adapter import AnthropicProvider
from openscire.provider.base import HealthStatus, ModelProvider, ProviderConfig, RateLimitConfig
from openscire.provider.capabilities import (
    CapabilityProbe,
    strip_unsupported,
    tool_call_to_canonical,
    tool_to_provider,
)
from openscire.provider.cascade import CascadeConfig, CascadeProvider
from openscire.provider.factory import select_provider
from openscire.provider.gemini_adapter import GeminiProvider
from openscire.provider.guarded import create_guarded_provider
from openscire.provider.litellm_adapter import (
    LiteLLMProvider,
    LiteLLMRouterConfig,
    LiteLLMRouterProvider,
)
from openscire.provider.mcp import MCPProvider, MCPServerConfig
from openscire.provider.models import (
    ChatMessage,
    Chunk,
    ContentPart,
    FallbackInfo,
    FinishReason,
    ImagePart,
    ModelCapabilities,
    ModelCard,
    ModelInfo,
    ProviderMetrics,
    TextPart,
)
from openscire.provider.openai_adapter import OpenAICompatibleProvider
from openscire.provider.quantization import (
    QuantizationResult,
    SystemResources,
    check_resource_warning,
    detect_from_name,
    detect_from_ollama_details,
    estimate_model_memory_gb,
    get_system_resources,
    is_unquantized,
)
from openscire.provider.registry import ModelRegistry, get_global_registry

__all__ = [
    "AnthropicProvider",
    "CapabilityProbe",
    "CascadeConfig",
    "CascadeProvider",
    "create_guarded_provider",
    "GeminiProvider",
    "LiteLLMProvider",
    "LiteLLMRouterConfig",
    "LiteLLMRouterProvider",
    "ModelProvider",
    "ProviderConfig",
    "RateLimitConfig",
    "HealthStatus",
    "ChatMessage",
    "Chunk",
    "ContentPart",
    "FallbackInfo",
    "FinishReason",
    "ImagePart",
    "ModelInfo",
    "ModelCard",
    "ModelCapabilities",
    "ProviderMetrics",
    "TextPart",
    "MCPProvider",
    "MCPServerConfig",
    "OpenAICompatibleProvider",
    "QuantizationResult",
    "SystemResources",
    "check_resource_warning",
    "detect_from_name",
    "detect_from_ollama_details",
    "estimate_model_memory_gb",
    "get_system_resources",
    "is_unquantized",
    "select_provider",
    "strip_unsupported",
    "tool_call_to_canonical",
    "tool_to_provider",
    "ModelRegistry",
    "get_global_registry",
]
