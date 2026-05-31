# Phase 2 — Model Provider Interface (MPI)

**Duration**: 3 weeks (Jul 2026)
**Dependencies**: Phase 1 (core models, config, provenance)
**Output**: Model-agnostic provider abstraction with adapters for OpenAI-compatible, Anthropic, Gemini

---

### Task 2.1: Abstract Base Provider

- [ ] 2.1.1: `ModelProvider` abstract base class with methods:
  - `stream_chat(messages, tools, config)` → `AsyncIterable[Chunk]`
  - `list_models()` → `List[ModelInfo]`
  - `supports_tool_use()` → `bool`
  - `supports_vision()` → `bool`
  - `supports_streaming()` → `bool`
  - `get_token_count(text)` → `int`
  - `get_context_window()` → `int`
  - `get_model_card()` → `ModelCard`
- [ ] 2.1.2: `ModelInfo` — id, name, provider, context_window, capabilities (flags), quantization_types (if local), pricing (if API-based)
- [ ] 2.1.3: `ModelCard` — provider, training_data_summary, known_biases, evaluation_results, intended_use, limitations, safety_ratings
- [ ] 2.1.4: `ChatMessage` — role (system, user, assistant, tool), content, tool_calls, tool_call_id
- [ ] 2.1.5: `Chunk` — delta_content, finish_reason, usage (prompt_tokens, completion_tokens), tool_calls (incremental)
- [ ] 2.1.6: `ProviderConfig` — api_key (encrypted), base_url, default_model, timeout, max_retries, rate_limit_config
- [ ] 2.1.7: Provider health check — `provider.health()` returns `(status, latency_ms, error_message)`

### Task 2.2: OpenAI-Compatible Adapter

- [ ] 2.2.1: `OpenAICompatibleProvider` — implements `ModelProvider`
- [ ] 2.2.2: `/chat/completions` streaming support (server-sent events)
- [ ] 2.2.3: Tool/function calling support (when available)
- [ ] 2.2.4: Vision/image input support (when available)
- [ ] 2.2.5: Model list endpoint parsing (`/models`)
- [ ] 2.2.6: Token counting via `tiktoken` (when model is known) or heuristic fallback
- [ ] 2.2.7: Compatible with Ollama, vLLM, LM Studio, Groq, Together, Fireworks, Perplexity, OpenRouter
- [ ] 2.2.8: Custom base URL and API key header support
- [ ] 2.2.9: Authentication: Bearer token, custom header, no-auth (local)

### Task 2.3: Anthropic Adapter

- [ ] 2.3.1: `AnthropicProvider` — implements `ModelProvider` via Anthropic Python SDK
- [ ] 2.3.2: Messages API streaming support
- [ ] 2.3.3: Tool use (`tool_use` content block)
- [ ] 2.3.4: Extended thinking mode support (when available)
- [ ] 2.3.5: Model list and capability detection

### Task 2.4: Google Gemini Adapter

- [ ] 2.4.1: `GeminiProvider` — implements `ModelProvider` via Google AI SDK
- [ ] 2.4.2: Content generation API streaming
- [ ] 2.4.3: Function calling
- [ ] 2.4.4: Model capability detection per model name

### Task 2.5: Local Model Quantization Awareness

- [ ] 2.5.1: Detect quantization format from model metadata (GGUF, EXL2, AWQ, GPTQ, bitsandbytes)
- [ ] 2.5.2: Query local inference servers for running models and their configs
- [ ] 2.5.3: Report quantization info in `ModelInfo` for local adapters
- [ ] 2.5.4: Warn when running unquantized models on resource-constrained hardware

### Task 2.6: Fallback Cascade

- [ ] 2.6.1: Configure ordered fallback chain (e.g., Ollama → smaller local → BYOK API → fail)
- [ ] 2.6.2: Automatic fallback on: connection error, timeout, rate limit, auth failure, model overload
- [ ] 2.6.3: User consent prompt before falling back to a different provider (opt-out for power users)
- [ ] 2.6.4: Fallback logging to provenance (which provider was used, why, latency)
- [ ] 2.6.5: Graceful degradation: if vision not available, send text-only; if tools not available, use constrained prompt

### Task 2.7: MCP Integration

- [ ] 2.7.1: `MCPProvider` — wraps Model Context Protocol client as a `ModelProvider` adapter
- [ ] 2.7.2: MCP tool discovery — query available MCP tools and their schemas
- [ ] 2.7.3: MCP tool execution — route tool calls through MCP server
- [ ] 2.7.4: MCP resource access — read resources (files, databases) through MCP
- [ ] 2.7.5: MCP configuration — server URL, auth, capabilities negotiation

### Task 2.8: Runtime Feature Detection

- [ ] 2.8.1: Capability probing — test model at connection time for tool use, vision, streaming
- [ ] 2.8.2: Capability caching — cache probes per model+provider combination
- [ ] 2.8.3: Graceful fallback when a capability is absent (no tool call → reformat as text prompt)
- [ ] 2.8.4: Provider-agnostic tool format conversion (tool schemas → provider-native format)
- [ ] 2.8.5: `ModelRegistry` — central registry mapping provider+model → `ModelInfo` with cached capabilities

### Task 2.9: BYOK Config Module

- [ ] 2.9.1: `BYOKConfig` — api_key, base_url, custom_headers, model_id, provider_type
- [ ] 2.9.2: Encrypted storage at rest (AES-256-GCM with key derived from user passphrase)
- [ ] 2.9.3: Key storage: OS keyring (macOS Keychain, Linux Secret Service, Windows Credential Manager) with file fallback
- [ ] 2.9.4: BYOK config import/export (encrypted portable format)
- [ ] 2.9.5: Multiple BYOK profiles (switch between personal API key and lab enterprise key)

### Task 2.10: LiteLLM Router Integration

- [ ] 2.10.1: `LiteLLMProvider` — wraps LiteLLM as a `ModelProvider` implementation
- [ ] 2.10.2: Leverage LiteLLM's provider list for automatic adapter selection
- [ ] 2.10.3: LiteLLM cost tracking passthrough
- [ ] 2.10.4: LiteLLM rate limiting and retry configuration
- [ ] 2.10.5: Fallback integration with LiteLLM's model fallback lists

### Task 2.11: MPI Tests

- [ ] 2.11.1: Unit tests for `ModelProvider` abstract class (contract enforcement)
- [ ] 2.11.2: Mock server for OpenAI-compatible API testing
- [ ] 2.11.3: Unit tests for each adapter with mock responses
- [ ] 2.11.4: Integration test: connect to local Ollama (if available) or mock
- [ ] 2.11.5: Fallback cascade integration test
- [ ] 2.11.6: Feature detection unit tests
- [ ] 2.11.7: BYOK encryption round-trip test
- [ ] 2.11.8: MCP adapter test (with mock MCP server)

---

**Phase 2 Exit Criteria**: All adapters pass unit tests. Streaming, tool use, fallback cascade all verified. BYOK config encrypts/decrypts correctly.
