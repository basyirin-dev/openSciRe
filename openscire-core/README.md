# openSciRe Core

Local-first, epistemically honest research AI toolkit for scientists.

## Status

**Phase 2 complete.** Provider abstraction layer, BYOK encryption, MCP
integration, and provenance tracking are implemented. See
[CHANGELOG.md](../CHANGELOG.md) for details.

## Installation

```bash
pip install -e ".[dev]"       # development (ruff, pytest, mypy)
pip install -e ".[byok]"      # Bring Your Own Key (cryptography, keyring)
pip install -e ".[mcp]"       # MCP tool integration
pip install -e ".[router]"    # LiteLLM router for multi-model fallback
```

## Architecture

```
openscire-core/src/openscire/
├── config/       # Configuration, env binding, BYOK key management
├── exceptions/   # Structured error hierarchy
├── logging/      # Structured logging with secret redaction
├── models/       # Domain models (claims, hypotheses, provenance entries)
├── provenance/   # Tracking, signing, graph, export (RO-Crate, W3C PROV-O)
├── provider/     # Model provider abstraction (OpenAI, Anthropic, Gemini, LiteLLM)
└── serialization/# JSON/YAML serialization
```

## Quick Start

```python
from openscire.provider import select_provider, ChatMessage

provider = select_provider("gpt-4o")
async for chunk in provider.stream_chat([ChatMessage.user("Hello")]):
    print(chunk.delta_content, end="")
```

## Test Suite

```bash
pytest -v --cov=openscire
```

567 tests, 84% coverage.
