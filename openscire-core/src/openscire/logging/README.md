# openSciRe — Logging

Purpose: Provides structured, scientific-grade logging with a custom `SCIENCE` log level, context manager for traceability, sensitive data redaction, and configurable output formatters.

Status: Stable

Public API:
- `SCIENCE_LEVEL_NUM` — Numeric value for the custom SCIENCE log level (between DEBUG and INFO)
- `LogContext` — Context manager that injects structured metadata (claim_id, hypothesis_id, etc.) into all log records
- `configure` — One-shot logging configuration (formatter, level, output destination, redaction rules)
- `get_logger` — Returns a `structlog` logger bound to the calling module's name
