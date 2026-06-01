# openSciRe — Provider

Purpose: Abstract model provider interface and adapters for LLM inference, supporting OpenAI-compatible APIs with provider-agnostic metrics, model cards, and chat message types.

Status: In Development

Public API:
- `ModelProvider` (ABC) — Abstract base class with `complete()`, `stream_complete()`, `embed()`, metrics collection, and rate limiting
- `ProviderConfig` — Pydantic model for provider connection settings (endpoint, API key, timeout, rate limits)
- `OpenAIAdapter` — OpenAI-compatible API adapter supporting chat completions, streaming, embeddings, and model listing
- `ChatMessage` — Dataclass for chat messages (role, content, tool_calls, metadata)
- `Chunk` — Dataclass for streaming completion chunks (delta, finish_reason, usage)
- `ModelInfo` — Model metadata (name, provider, context window, pricing, capabilities)
- `ModelCard` — Extended model information including capabilities, tier, and description
- `ModelCapabilities` — Dataclass describing model features (function_calling, streaming, vision, embeddings, json_mode)
- `ProviderMetrics` — Dataclass tracking per-request metrics (latency, token counts, cost)
