# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-06-02

### Added

- **Provider abstraction layer** (Phase 2) — `ModelProvider` ABC with concrete `stream_chat`, abstract `_do_stream_chat`, `RateLimitConfig`, `HealthStatus`, `get_capabilities()` virtual method
- **OpenAI-compatible adapter** — `OpenAICompatibleProvider` via raw `httpx`, SSE parser, tool calling, vision, tiktoken token counting, model list endpoint, quantization detection
- **Anthropic Claude adapter** — `AnthropicProvider` via raw `httpx`, event-type SSE, extended thinking mode (`Chunk.thinking`), content block handling, tool calling, error mapping
- **Google Gemini adapter** — `GeminiProvider` via raw `httpx`, data-only SSE, system instruction, inlineData vision, model list with hardcoded fallback, finish reason mapping
- **Local quantization awareness** — `detect_from_name()` (GGUF/AWQ/GPTQ/EXL2/bitsandbytes regex), `detect_from_ollama_details()`, `estimate_model_memory_gb()`, `check_resource_warning()`
- **Fallback cascade** — `CascadeProvider` decorator with ordered fallback, `_FALLBACK_TRIGGERS`, `strip_unsupported()` for graceful degradation, consent callback, provenance logging for fallback events
- **MCP integration** — `MCPProvider` decorator over chat provider + MCP servers (stdio transport), tool auto-discovery with `{server}__{tool}` prefix, resource listing/reading
- **Runtime feature detection** — `CapabilityProbe` (heuristic table + pattern matchers + LRU cache), `ModelRegistry` (global singleton, lazy resolution, `find()` by capability/provider)
- **BYOK config module** — `BYOKProfile`, `CryptoEngine` (AES-256-GCM via `cryptography`, `pynacl.SecretBox` fallback), `KeyStore` (OS keyring primary, file fallback), `BYOKManager` (CRUD, active profile, `.byok` portable export)
- **LiteLLM Router integration** — `LiteLLMProvider` wrapping `litellm.acompletion()`, `LiteLLMRouterProvider` with fallback signaling via `success_callback`, `from_litellm_yaml()`, explicit-first `select_provider()` factory
- **Provenance pervasiveness** — `ProviderConfig.provenance_tracker` field, automatic input/output/error provenance recording in `stream_chat`, `_ProvenanceTrackerProtocol`, cascade fallback events linked via `provenance_parent_id`
- **Provider provenance tests** — 6 unit tests (input/output/error recording, broken tracker resilience, parent linking, no-tracker pass-through)
- **Integration tests** — provenance-through-provider full cycle (3 tests), provenance security (no secrets in parameters_snapshot, signed entries, 2 tests)
- **OLLAMA_HOST env var** — integration tests read `OLLAMA_HOST` (default `localhost:11434`) instead of hardcoded address
- **Coverage enforcement** — `--cov-fail-under=75` in pytest config

### Changed

- `stream_chat` refactored from abstract method to concrete wrapper; subclasses implement `_do_stream_chat` instead
- `CascadeProvider._log_fallback` accepts and forwards `provenance_parent_id`
- All 21 source modules now have module-level docstrings
- `openscire-core/README.md` created with package overview

### Documentation

- Module-level docstrings added to all 20 previously undocumented source files
- `openscire-core/README.md` created
- Cross-cutting checklist items all checked (Provenance, Testing, Documentation)
- `docs/phases/02_model_provider.md`: Task 2.11.4 (Ollama integration) checked

### Testing

- **567 tests** total (up from 556), all passing
- 84.4% line coverage (above 75% threshold)
- 6 new unit tests for provenance-through-provider
- 5 new integration tests: provenance full cycle (3), provenance security (2)
- `OLLAMA_HOST` env var support for portable Ollama testing

### Security

- Security integration tests verify API keys don't leak into provenance `parameters_snapshot`
- Signed provenance entries verified to not contain plaintext secrets

## [0.1.0] — 2026-06-01

### Added

- **Repository & agent infrastructure** — `.gitignore`, `.gitattributes`, Apache 2.0 license, commercial license placeholder, security documentation (`SECURITY.md`, `RESPONSIBLE_DISCLOSURE.md`, `docs/threat-model.md`), GitHub issue/PR templates, `CONTRIBUTING.md`, `CODEOWNERS`, `CITATION.cff`, `codemeta.json`
- **Project configuration** — `pyproject.toml` (hatchling build, ruff/mypy/pytest/coverage config), `Cargo.toml` (workspace root), `Makefile` (install/lint/format/typecheck/test/clean/build/all), `.pre-commit-config.yaml`
- **Critique library** — 8 documents (01–08) with philosophical and structural analysis of Google Gemini for Science
- **Documentation framework** — `docs/business-brief.md`, `docs/phase-roadmap.md`, 19 phase task breakdowns, cross-cutting concerns, risk register
- **Rust scaffold** — `openscire-sandbox-core` workspace member with placeholder library and test
- **`openscire-core` package scaffolding** — Core package with `src/openscire/` directory structure and 7 subpackages
- **Core Pydantic models** — `ScientificClaim`, `Evidence`, `Hypothesis`, `ProvenanceEntry`, `LiteratureReference`, `ResearchContext`, `ReproducibilityBundle` with supporting enums (`EvidenceType`, `HypothesisStatus`, `VerificationStatus`, `ReproducibilityStatus`)
- **Philosophy foundation models** — `KnowledgeBoundaryFlag`, `EpistemicMarker`, `FalsificationConfig`, `AgentDiversityConfig`, `AgentModelProvider`, `AgentTemperatureConfig`, `BoundaryCategory`, `SourceCategory`
- **Config module** — `Config` class (Pydantic `BaseSettings`) with env variable overrides (`OPENSCIRE_` prefix), YAML/TOML parsing, sub-config models (`ModelConfig`, `ProvenanceConfig`, `LoggingConfig`, `LiteratureConfig`, `EthicsConfig`, `SandboxConfig`), secret redaction (via `SecretStr`), reproducibility bundle export
- **Logging module** — Structured JSON logging via `structlog`, custom `SCIENCE` log level, `LogContext` context manager, sensitive data redaction, `configure()` and `get_logger()` API
- **Provenance module** — `ProvenanceTracker` (high-level operation recording), `ProvenanceGraph` (DAG with cycle detection, topological sort, subgraph queries), cryptographic signing (Ed25519 via `sign_entry`/`verify_entry`/`content_hash`), pluggable `StorageBackend` abstraction (`InMemoryBackend`, `SQLiteBackend`, `PostgresBackend`), `ProvenanceExporter` (JSON, RO-Crate, W3C PROV-N), `ResearchChronologyEnforcer`
- **Serialization module** — `Serializer` with JSON/YAML/MessagePack format dispatch, versioned `SerializationEnvelope` with `CURRENT_SERIALIZATION_VERSION`, `SchemaVersionMismatchError`, `UnknownFormatError`, `SUPPORTED_FORMATS`
- **Exceptions module** — `openSciReError` hierarchy with 6 exception classes (`ProvenanceError`, `ConfigError`, `ModelProviderError`, `EthicsError`, `ValidationError`)
- **Provider module** (Phase 2, In Development) — `ModelProvider` ABC, `OpenAIAdapter`, `ProviderConfig`, provider models (`ProviderMetrics`, `ChatMessage`, `Chunk`, `ModelInfo`, `ModelCard`, `ModelCapabilities`)
- **Test suite** — 169 tests with 90%+ code coverage, including unit tests and cross-phase integration tests

### Security

- Secrets redacted in log output via regex-based `_redact_processor`
- Cryptographic signing (Ed25519) of all provenance entries
- `SecretStr` for API keys in config models
- Prohibited-use detection in ethics guardrails

### Fixed

- `CITATION.cff` `date-released` format (YYYY-MM → YYYY-MM-DD) and DOI placeholder pattern for CFF 1.2.0 schema compliance
- Cargo workspace `edition` field moved from workspace declaration to member crate
- Pre-commit hooks updated to latest revisions (ruff v0.11→v0.15, mypy v1.15→v2.1, pre-commit-hooks v5→v6)
