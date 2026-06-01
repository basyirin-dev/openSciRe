# openSciRe — Initial Threat Model

> **Status**: Phase 0 — preliminary. Will be updated as components are built.
> **Last reviewed**: June 2026

## Attack Surfaces

| Surface | Description | Risk Level | Mitigation |
|---------|-------------|------------|------------|
| Model provider API keys | User-provided keys for OpenAI, Anthropic, Gemini, etc. | **High** | BYOK encryption at rest; never logged |
| Prompt injection | Malicious input that bypasses Ethical Firewall | **High** | Input sanitization, risk tiering, adversarial testing |
| Provenance signing key | Ed25519 key used to sign research outputs | **Critical** | Key stored in OS keychain or env var; never persisted to disk unencrypted |
| Literature API tokens | Zotero, PubMed, Semantic Scholar API keys | **Medium** | Same BYOK encryption as model keys |
| Cached literature embeddings | Embedded vectors of scientific papers | **Low** | Local-only; no exfiltration path |
| Python code execution (sandbox) | User-authored or LLM-generated code run locally | **High** | Rust sandbox (Phase 9); filesystem/network restrictions |
| Jupyter extension | Cell magic that executes user code | **Medium** | Sandbox isolation; no network from execution context |

## Data Sensitivity Classification

| Class | Examples | Storage | Transmission |
|-------|----------|---------|--------------|
| Public | Published papers, embeddings | Unencrypted | TLS |
| User-private | API keys, research notes | Encrypted (age/AES-256-GCM) | Never transmitted off-device |
| Institutional | Lab data under pilot agreements | Encrypted at rest | TLS + customer-managed key |

## Trust Boundaries

1. **User ↔ Local System**: Trusted (same machine)
2. **Local System ↔ Model Provider API**: TLS with pinned certificates
3. **Local System ↔ Literature APIs**: TLS
4. **Local System ↔ Jupyter Kernel**: Inter-process on same host
5. **Future: Local System ↔ Team Server**: TLS + mutual auth (Phase 12+)

## Mitigation Priorities

1. **Immediate (Phase 0–3)**: API key security, input sanitization, provenance integrity
2. **Near-term (Phase 4–8)**: Literature API token management, Ethical Firewall hardening
3. **Medium-term (Phase 9)**: Rust sandbox for code execution
4. **Long-term (Phase 12+)**: Multi-tenant isolation, audit logging
