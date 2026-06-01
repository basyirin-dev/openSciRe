# Phase 2 — Model Provider Interface (MPI)

**Duration**: 3 weeks (Jul 2026)
**Dependencies**: Phase 1 (core models, config, provenance)
**Output**: Model-agnostic provider abstraction with adapters for OpenAI-compatible, Anthropic, Gemini

---

### Task 2.1: Abstract Base Provider

- [x] 2.1.1: `ModelProvider` abstract base class with methods:
  - `stream_chat(messages, tools, config)` → `AsyncIterable[Chunk]`
  - `list_models()` → `List[ModelInfo]`
  - `supports_tool_use()` → `bool`
  - `supports_vision()` → `bool`
  - `supports_streaming()` → `bool`
  - `get_token_count(text)` → `int`
  - `get_context_window()` → `int`
  - `get_model_card()` → `ModelCard`
- [x] 2.1.2: `ModelInfo` — id, name, provider, context_window, capabilities (flags), quantization_types (if local), pricing (if API-based)
- [x] 2.1.3: `ModelCard` — provider, training_data_summary, known_biases, evaluation_results, intended_use, limitations, safety_ratings
- [x] 2.1.4: `ChatMessage` — role (system, user, assistant, tool), content, tool_calls, tool_call_id
- [x] 2.1.5: `Chunk` — delta_content, finish_reason, usage (prompt_tokens, completion_tokens), tool_calls (incremental)
- [x] 2.1.6: `ProviderConfig` — api_key (encrypted), base_url, default_model, timeout, max_retries, rate_limit_config
- [x] 2.1.7: Provider health check — `provider.health()` returns `(status, latency_ms, error_message)`

### Task 2.2: OpenAI-Compatible Adapter

- [x] 2.2.1: `OpenAICompatibleProvider` — implements `ModelProvider`
- [x] 2.2.2: `/chat/completions` streaming support (server-sent events)
- [x] 2.2.3: Tool/function calling support (when available)
- [x] 2.2.4: Vision/image input support (when available)
- [x] 2.2.5: Model list endpoint parsing (`/models`)
- [x] 2.2.6: Token counting via `tiktoken` (when model is known) or heuristic fallback
- [ ] 2.2.7: Compatible with Ollama, vLLM, LM Studio, Groq, Together, Fireworks, Perplexity, OpenRouter
- [x] 2.2.8: Custom base URL and API key header support
- [x] 2.2.9: Authentication: Bearer token, custom header, no-auth (local)

### Task 2.3: Anthropic Adapter

- [x] 2.3.1: `AnthropicProvider` — implements `ModelProvider` via raw `httpx.AsyncClient`
- [x] 2.3.2: Messages API streaming support (event-type SSE parser)
- [x] 2.3.3: Tool use (`tool_use` content block with `input_json_delta`)
- [x] 2.3.4: Extended thinking mode support (`Chunk.thinking` field)
- [x] 2.3.5: Model list (hardcoded 9 Claude models) and capability detection

### Task 2.4: Google Gemini Adapter

- [x] 2.4.1: `GeminiProvider` — implements `ModelProvider` via raw `httpx.AsyncClient`
- [x] 2.4.2: Content generation API streaming (`data:` SSE parser)
- [x] 2.4.3: Function calling (`functionCall`/`functionResponse` content blocks)
- [x] 2.4.4: Model capability detection per model name

### Task 2.5: Local Model Quantization Awareness

- [x] 2.5.1: Detect quantization format from model metadata (GGUF, EXL2, AWQ, GPTQ, bitsandbytes)
- [ ] 2.5.2: Query local inference servers for running models and their configs (Ollama provider not yet built; `detect_from_ollama_details()` utility is ready)
- [x] 2.5.3: Report quantization info in `ModelInfo` for local adapters (integrated into `OpenAICompatibleProvider.list_models()`)
- [x] 2.5.4: Warn when running unquantized models on resource-constrained hardware

### Task 2.6: Fallback Cascade

- [x] 2.6.1: Configure ordered fallback chain — `CascadeProvider(cascade=[(name, provider), ...])`
- [x] 2.6.2: Automatic fallback on: connection error (`httpx.ConnectError`), timeout (`TimeoutError`), rate limit (`MODEL_RATE_LIMIT`), 5xx / connection failure (`MODEL_CONNECTION_FAILURE`), auth failure (`MODEL_AUTH_FAILURE` — opt-in via `include_auth_fallback`)
- [x] 2.6.3: User consent callback — `CascadeProvider(consent_callback=...)` called before each fallback when `CascadeConfig(user_consent=True)`. Callback returns `True`/`False` to allow or deny. Default `user_consent=False` for headless use.
- [x] 2.6.4: Fallback logging to provenance — `CascadeProvider(provenance_tracker=...)` with `CascadeConfig(log_to_provenance=True)`. Falls back gracefully if no tracker is configured.
- [x] 2.6.5: Graceful degradation — strips `ImagePart` from messages when child lacks vision; strips `tools` param and adds "text-only assistant" system message when child lacks tool use. Disabled via `CascadeConfig(graceful_degradation=False)`.

### Task 2.7: MCP Integration

- [x] 2.7.1: `MCPProvider` — wraps a chat ``ModelProvider`` as a ``ModelProvider`` adapter with MCP tool/resource support
- [x] 2.7.2: MCP tool discovery — ``list_mcp_tools()`` queries all configured MCP servers, returns OpenAI-compatible tool schemas with prefixed names
- [x] 2.7.3: MCP tool execution — ``execute_mcp_tool(full_name, arguments)`` routes to the correct MCP server via prefixed name (``{server}__{tool}``)
- [x] 2.7.4: MCP resource access — ``list_mcp_resources()`` / ``read_mcp_resource(uri)`` reads files, databases through MCP
- [x] 2.7.5: MCP configuration — ``MCPServerConfig`` dataclass (name, command, env, enabled). Stdio transport only. SDK via ``openscire-core[mcp]`` optional extra.

### Task 2.8: Runtime Feature Detection

- [x] 2.8.1: Capability probing — `CapabilityProbe` class with heuristic table (25+ models), pattern matching, opt-in runtime probe. Discovered via `discover(provider_name, model_id)` with LRU cache.
- [x] 2.8.2: Capability caching — `CapabilityProbe._cache` (OrderedDict, max 256 entries). Cache keyed by `(provider, model)`. `invalidate()` for single entry, per-provider, or full flush.
- [x] 2.8.3: Graceful fallback — `strip_unsupported(messages, tools, capabilities)` strips `ImagePart` when vision absent; strips tools+adds system message when tool_use absent. Replaces `cascade.py`'s ad-hoc `_preprocess`. Added `MODEL_UNSUPPORTED_CAPABILITY` to `_FALLBACK_TRIGGERS`.
- [x] 2.8.4: Provider-agnostic tool format conversion — `tool_to_provider(tools, provider)` converts canonical (OpenAI) format to Anthropic/Gemini native. `tool_call_to_canonical(tool_calls, provider)` converts back.
- [x] 2.8.5: `ModelRegistry` — `ModelRegistry` class with `get()`, `register()`, `register_many()`, `find()`, `clear()`. Lazy capability resolution via `CapabilityProbe` or provider instance. Global singleton `get_global_registry()`.
- [x] 2.8.6: Provider adapter overrides — `get_capabilities(model_id)` on `ModelProvider` base class (default: `supports_*`). `OpenAICompatibleProvider`, `AnthropicProvider`, `GeminiProvider` all override with model-specific heuristics.
- [x] 2.8.7: Tests — `test_capabilities.py` (30 tests), `test_registry.py` (17 tests). 47 total for task 2.8.

### Task 2.9: BYOK Config Module

- [x] 2.9.1: `BYOKConfig` — api_key, base_url, custom_headers, model_id, provider_type
- [x] 2.9.2: Encrypted storage at rest (AES-256-GCM with key derived from user passphrase)
- [x] 2.9.3: Key storage: OS keyring (macOS Keychain, Linux Secret Service, Windows Credential Manager) with file fallback
- [x] 2.9.4: BYOK config import/export (encrypted portable format)
- [x] 2.9.5: Multiple BYOK profiles (switch between personal API key and lab enterprise key)

### Task 2.10: LiteLLM Router Integration

- [x] 2.10.1: `LiteLLMProvider` — wraps LiteLLM as a `ModelProvider` implementation
- [x] 2.10.2: Leverage LiteLLM's provider list for automatic adapter selection
- [x] 2.10.3: LiteLLM cost tracking passthrough
- [x] 2.10.4: LiteLLM rate limiting and retry configuration
- [x] 2.10.5: Fallback integration with LiteLLM's model fallback lists

### Task 2.11: MPI Tests

- [x] 2.11.1: Unit tests for `ModelProvider` abstract class (contract enforcement) — 12 tests in ``test_provider.py``
- [x] 2.11.2: Mock server for OpenAI-compatible API testing — ``respx`` with SSE fixtures in ``TestOpenAIProvider``
- [x] 2.11.3: Unit tests for each adapter with mock responses — 124 tests across OpenAI/Anthropic/Gemini/LiteLLM
- [x] 2.11.4: Integration test: connect to local Ollama (if available) or mock
- [x] 2.11.5: Fallback cascade integration test — 29 tests in ``test_cascade.py``
- [x] 2.11.6: Feature detection unit tests — 47 tests in ``test_capabilities.py`` and ``test_registry.py``
- [x] 2.11.7: BYOK encryption round-trip test — 35 tests in ``test_byok.py``
- [x] 2.11.8: MCP adapter test (with mock MCP server) — 28 tests in ``test_mcp.py``

---

**Phase 2 Exit Criteria**: All adapters pass unit tests. Streaming, tool use, fallback cascade all verified. BYOK config encrypts/decrypts correctly.
