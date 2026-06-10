# openSciRe — Ethics Layer

Purpose: Multi-layered ethical guardrails for LLM-powered research — DURC detection, risk tiering
(differential speed governance), data sovereignty, indigenous knowledge protection, carbon budget
tracking, source grounding verification, confabulation detection, and verification asymmetry
analysis.

Status: Stable (Phase 3)

Public API:

- `EthicalFirewall` — Configurable firewall with DURC scanning (keyword/embedding/LLM), tier
  classification, sovereignty checks, indigenous knowledge checks, carbon tracking, and source
  grounding. Wraps `ModelProvider` via `wrap()` to return a `FirewalledProvider`
- `FirewalledProvider` — `ModelProvider` wrapper that intercepts `stream_chat()` with
  prompt/response scanning, ethical warning injection, carbon annotation, and grounding verification
- `ConfabulationDetector` — Post-generation analysis for hallucination/confabulation patterns using
  knowledge boundary flags and contradiction detection
- `VerificationAsymmetryTracker` — Tracks verification asymmetry: the structural imbalance where
  positive claims are harder to verify than negative claims
- `SourceGroundingEngine` — Extracts citations from generated text, verifies them against known
  sources, and flags unsupported claims
- `CarbonBudgetTracker` — Per-query carbon estimation with monthly budget enforcement and
  equivalence display
- `DataSovereigntyChecker` — Evaluates data provenance (origin, consent, export restrictions)
  against sovereignty constraints
- `IndigenousKnowledgeProtector` — Evaluates indigenous data against CARE principles (Collective
  Benefit, Authority, Responsibility, Ethics)
- `TierClassifier` — Risk tier classification (High/Medium/Low) with domain detection and governance
  action assignment
- `FirewallAuditLog` — SQLite-backed append-only audit log with optional Ed25519 signing
