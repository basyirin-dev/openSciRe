# Project Skepsis

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](pyproject.toml)
[![CI](https://img.shields.io/badge/CI-not_yet_configured-lightgrey.svg)](docs/phase-roadmap.md)

> **Local-first, open-source, epistemically honest research AI for scientists.**

Skepsis exists because existing "AI for science" tools — Google's Gemini for Science
in particular — are structurally dangerous: cloud-locked, epistemically opaque, and
designed for vendor capture rather than research integrity.

We build the alternative.

## Philosophical Stance

Most AI-for-science tools optimize for *plausibility* — generating outputs that
*sound right* — rather than *falsifiability* — supporting claims that *can be tested*.
This is not a technical bug; it is a design philosophy that treats scientific reasoning
as a text-generation problem rather than an epistemic one.

Skepsis inverts this. We build from the insight that the most valuable thing an AI
research assistant can say is **"I don't know — and here's how to find out."**

For the full philosophical grounding, see the [critiques manifesto](critiques/README.md).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Skepsis Core                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Literature│  │   RAG    │  │  Agents  │  │ Hypothesis │  │
│  │  Engine   │  │  Engine  │  │ Framework│  │ Generator  │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Ethics  │  │  Model   │  │Provenance│  │  Sandbox   │  │
│  │  Layer   │  │ Provider │  │ Tracker  │  │  (Rust)    │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │               CLI / Jupyter / Web UI                    │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
       │                  │                   │
       ▼                  ▼                   ▼
  Local Models      Cloud APIs          Literature APIs
  (Ollama/vLLM)   (OpenAI/Anthropic)   (PubMed/arXiv/Zotero)
```

For the phased development plan, see [`docs/phase-roadmap.md`](docs/phase-roadmap.md).

## Quick Start

```bash
# Prerequisites: Python 3.12+, Rust toolchain (for sandbox)
pip install skepsis-core

# Configure your first model provider
skepsis provider add openai --api-key "$OPENAI_KEY"

# Start a literature review
skepsis literature search "CRISPR off-target effects deep learning"
```

> **Note**: The package is under active development. CLI commands shown above are
> the target interface; not all are implemented yet. See the phase roadmap.

## Prerequisites

- **Python 3.12+**
- **Rust toolchain** (for optional sandboxed code execution)
- **Ollama** (recommended for local inference) or API keys for cloud providers

## Ethical Use

**This tool can be misused.** We've built layered defenses — an Ethical Firewall,
provenance tracking, epistemic uncertainty quantification — but no AI tool can
fully prevent harmful applications.

- Read our [Responsible Disclosure policy](RESPONSIBLE_DISCLOSURE.md)
- Report ethical concerns to `ethics@skepsis-research.dev`
- Prohibited uses include weapons development, human subjects research without
  IRB approval, surveillance, and research fraud

**Epistemic caveat**: All outputs from language models are fallible. Skepsis
surfaces uncertainty and requires source grounding, but it cannot guarantee
correctness. Treat generated content as a starting point for your own judgment.

## License

Apache 2.0 — see [`LICENSE`](LICENSE). Enterprise features available under
separate commercial license (see [`LICENSE-COMMERCIAL.md`](LICENSE-COMMERCIAL.md)).

## Status

Pre-alpha. Active development toward a Y Combinator S2027 application.
Pilot program for academic labs opening January 2027.
