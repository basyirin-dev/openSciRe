# openSciRe — Exceptions

Purpose: Defines a structured, provenance-aware exception hierarchy with symbolic error codes and
source attribution for all openSciRe subsystems.

Status: Stable

Public API:

- `openSciReError` — Base exception for all openSciRe errors
- `ProvenanceError` — Provenance tracking failures (signature mismatch, cycle detection, storage
  errors)
- `ConfigError` — Configuration loading/validation failures
- `ModelProviderError` — LLM provider communication or protocol errors
- `EthicsError` — Ethics guardrail violations (prohibited domain, category mismatch)
- `ValidationError` — Data model validation failures
