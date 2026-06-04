# Changelog

## Phase 3 — Ethical Checkpoints & Provenance Pervasiveness

### Added

- **`create_guarded_provider()`** in `openscire/provider/guarded.py`: factory that wraps any `ModelProvider` with the full `EthicalFirewall` guardrail stack — DURC scanning, RiskTier classification, cooling-off/human-checkpoint governance, source grounding with citation verification, and optional carbon cost tracking. Every checkpoint wired with `ProvenanceTracker` for transparent audit trails.

- **Provenance injection in data modules**:
  - `SourceGroundingEngine`: optional `provenance_tracker` param, records `citation_grounding` entries with flag/citation counts.
  - `Curator`: optional `provenance_tracker` param, records `curation_external_ratio`, `curation_adversarial_search`, and `curation_assumption_mining` entries.
  - `GapAnalyzer`: optional `provenance_tracker` param, records `gap_analysis` entry with per-type gap counts.
  - `CitationGraphAnalyzer`: optional `provenance_tracker` param, records `citation_graph_build` and `citation_graph_analysis` entries with node/edge/influence/cluster metrics.

### Changed

- All provenance recording uses graceful `try/except` swallowing — never blocks inference or analysis.
- All injected `provenance_tracker` params typed as `Any` (protocol duck-typing), optional, default `None`.

## Phase 2 — Model Provider Interface + Provenance

### Added

- 6 provider adapters (OpenAI, Anthropic, Gemini, LiteLLM, MCP, Cascade)
- BYOK (Bring Your Own Key) profile support
- Provenance tracking in `ModelProvider.stream_chat()` with input/output hashing
- Ed25519 cryptographic signing of provenance entries
- Provenance DAG for parent-child action linking

## Phase 1 — Foundation

### Added

- Project scaffold: Python package, Rust workspace, directory structure
- Critique library (8 documents): philosophical/structural analysis of AI-for-science tools
- Config, logging, exception framework
- Initial threat model and security posture
- Pre-commit hooks (ruff, mypy)
