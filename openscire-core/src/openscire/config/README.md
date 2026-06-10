# openSciRe — Config

Purpose: Provides the `Config` (Pydantic `BaseSettings`) model with per-subsystem sub-models,
environment variable overrides via the `OPENSCIRE_` prefix, and YAML/TOML file parsing.

Status: Stable

Public API:

- `Config` — Top-level application configuration with env/file loading, secret redaction, and
  reproducibility bundle export
- `ModelConfig` — LLM provider settings (endpoint, API key, model name, temperature, timeout)
- `ProvenanceConfig` — Provenance tracking settings (backend type, signing key path, export format)
- `LoggingConfig` — Structured logging configuration (level, format, output path)
- `LiteratureConfig` — Literature retrieval settings (Zotero API, search endpoints, cache TTL)
- `EthicsConfig` — Ethics guardrail parameters (enforcement level, prohibited domains)
- `SandboxConfig` — Code sandbox configuration (timeout, memory limit, allowed imports)
