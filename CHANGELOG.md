# Changelog

## Phase 6 — Multi-Agent Orchestration & Safety Layer

### Added

- **`SupervisorAgent`** in `openscire/agent/supervisor.py`: Central orchestrator with state machine
  (idle→planning→executing→reviewing→completed/failed), task queue with dependency resolution,
  configurable health monitoring, conflict resolution, human handoff, session persistence (JSON),
  diversity assignment, confabulation detection, and cross-agent citation validation.

- **`AgentBus`** in `openscire/agent/bus.py`: Singleton pub/sub message bus with 12 typed message
  types (task, result, query, response, review, flag, escalate, log, heartbeat), thread management,
  provenance persistence with DAG linking, and async non-blocking delivery.

- **`LiteratureReviewAgent`** in `openscire/agent/literature_review.py`: LLM-optional structured
  evidence-gathering with query decomposition, OpenAlex + PubMed multi-source search, dedup, quality
  scoring, gap analysis, contradiction detection (negation-based heuristic), and retraction
  monitoring.

- **`FalsificationAgent`** in `openscire/agent/falsification.py`: Popperian falsification pipeline
  (search → counter-examples → confounds → alternatives → critique → report), regex-based claim
  extraction from causal connectors, and auto-submission to `NegativeResultRegistry`.

- **`EthicsAgent`** in `openscire/agent/ethics_agent.py`: Ethical review pipeline (scan firewall →
  classify tier → flag dual-use → check sovereignty → estimate carbon → escalate if needed),
  non-blocking dependency failure, and structured `EthicsReport` with `model_dict()`.

- **`WorkflowOrchestrator`** in `openscire/agent/workflow.py`: Template-driven workflow execution
  with `WorkflowBuilder` (fluent API), 3 predefined templates (literature→falsification, hypothesis
  full-cycle, contradiction detection), ResearchPlan generation, progress tracking with CPM
  bottleneck detection, and provenance recording.

- **`DiversityManager`** in `openscire/agent/diversity.py`: Guarantees unique (provider, model,
  temperature, objective) tuples per agent role via 3-stage cascade: explicit config → temperature
  defaults → 5-objective cycling → aggressive fallback (8 temps × 8 models × 4 providers).

### Changed

- `SupervisorAgent.__init__` now accepts optional `diversity_manager`, `confabulation_detector`,
  `source_enforcer` parameters for downstream safety rail integration.
- `start_session()` now accepts optional `plan: ResearchPlan` parameter for external plan injection.

### Tests

- 256 new tests across 7 test files: 25 diversity, 159 supervisor, 54 workflow, 20 bus, 35 ethics
  agent, 23 falsification agent, 18 supervisor safety integration.
- All tests pass with 86%+ total coverage.

### Added

- **`DocumentChunker`** in `openscire/references/chunking/`: narrative structure-preserving document
  chunker with IMRaD section detection, citation-anchored splits, figure/table proximity,
  configurable overlap, list/code block preservation, and full chunk metadata.

- **`CitationContextWindow`** in `openscire/references/citation/`: citation neighborhood analysis
  (citing/cited-by graph traversal), density scoring (z-score with high/medium/low labels), temporal
  weighting (exponential decay), and contradiction detection via retraction monitor.

- **`ContextWindowManager`** in `openscire/references/context/`: token budget tracking,
  priority-based inclusion, dynamic compression with overflow strategy, structured context packaging
  for model consumption, and model-specific context limits.

- **`SourceEnforcer`** in `openscire/references/enforcer/`: citation extraction and verification,
  three enforcement modes (`strict`/`warn`/`audit`), Jaccard-based citation suggestion (threshold
  0.05, top-3), and `SemanticCrossChecker` for LLM-based claim-vs-source verification with 5
  verdicts (supports/contradicts/insufficient_evidence/ambiguous/unverifiable).

- **`CitationFormatter`** in `openscire/references/formatter/`: 7 built-in styles (APA, Nature,
  Science, Vancouver, IEEE, Chicago, ACS) with configurable `StyleConfig`, inline + reference list
  formatting, Oxford comma for `&`, DOI linking, and standalone
  `to_bibtex()`/`to_ris()`/`to_csl_json()` export functions.

- **`PedagogicalReportBuilder`** in `openscire/references/report/`: 7-section pedagogical report
  (Executive Summary through Provenance), fluent builder API ingesting
  `GapReport`/`SourceEnforcementReport`/`CrossCheckResult`/metadata, with 3 export formats
  (Markdown, Jupyter notebook via nbformat v4 JSON, RO-Crate 1.1 JSON-LD). Explicitly no
  audio/video/slide-deck artifact modes.

- **`HybridRetriever`** in `openscire/references/retrieval/`: dense + sparse retrieval via RRF
  fusion, pure-Python BM25Okapi (no `rank_bm25` dep), fielded search index, query expansion with
  ~60-entry scientific synonym dictionary, and cross-encoder reranking integration.

### Changed

- `openscire/references/__init__.py` now exports ~30 new public symbols across 7 sub-packages.

### Tests

- 229 new tests across 8 test files (unit + integration)
- 3 integration tests for ethical checkpoint cycle, retraction cycle, full RAG pipeline
- All tests pass with 85.24% coverage

## Phase 3 — Ethical Checkpoints & Provenance Pervasiveness

### Added

- **`create_guarded_provider()`** in `openscire/provider/guarded.py`: factory that wraps any
  `ModelProvider` with the full `EthicalFirewall` guardrail stack — DURC scanning, RiskTier
  classification, cooling-off/human-checkpoint governance, source grounding with citation
  verification, and optional carbon cost tracking. Every checkpoint wired with `ProvenanceTracker`
  for transparent audit trails.

- **Provenance injection in data modules**:

  - `SourceGroundingEngine`: optional `provenance_tracker` param, records `citation_grounding`
    entries with flag/citation counts.
  - `Curator`: optional `provenance_tracker` param, records `curation_external_ratio`,
    `curation_adversarial_search`, and `curation_assumption_mining` entries.
  - `GapAnalyzer`: optional `provenance_tracker` param, records `gap_analysis` entry with per-type
    gap counts.
  - `CitationGraphAnalyzer`: optional `provenance_tracker` param, records `citation_graph_build` and
    `citation_graph_analysis` entries with node/edge/influence/cluster metrics.

### Changed

- All provenance recording uses graceful `try/except` swallowing — never blocks inference or
  analysis.
- All injected `provenance_tracker` params typed as `Any` (protocol duck-typing), optional, default
  `None`.

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
