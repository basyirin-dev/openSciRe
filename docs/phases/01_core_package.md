# Phase 1 — Core Python Package (Provenance-Native)

**Duration**: 3 weeks (Jul 2026)
**Dependencies**: Phase 0, Phase 0.5 (go decision)
**Output**: Installable `openscire-core` package with provenance-native architecture

---

### Task 1.1: Package Directory Structure

- [x] 1.1.1: Create `openscire-core/` at project root
- [x] 1.1.2: Create `openscire-core/src/openscire/__init__.py` with version string
- [x] 1.1.3: Create subpackage directories: `models/`, `config/`, `provenance/`, `logging/`, `exceptions/`, `serialization/`
- [x] 1.1.4: Create `__init__.py` in each subpackage
- [x] 1.1.5: Create `openscire-core/tests/` with `__init__.py` and `conftest.py`
- [x] 1.1.6: Create `openscire-core/tests/unit/` and `openscire-core/tests/integration/`
- [x] 1.1.7: Verify `pip install -e ./openscire-core` works and `import openscire` succeeds

### Task 1.2: Base Pydantic Models

- [x] 1.2.1: `ScientificClaim` — field, evidence_chain, confidence_interval, source_references, verification_status, timestamp, created_by
- [x] 1.2.2: `Evidence` — type (experimental, computational, literature, anecdotal), source, strength_rating, reproducibility_status, date_collected
- [x] 1.2.3: `Hypothesis` — claim, null_hypothesis, falsification_criteria, testability_score, domain_tags, related_literature, status (proposed, tested, supported, refuted)
- [x] 1.2.4: `ProvenanceEntry` — action_id, parent_ids, agent_id, model_id, parameters_snapshot, input_hash, output_hash, timestamp, cryptographic_signature
- [x] 1.2.5: `LiteratureReference` — doi, title, authors, journal, year, citation_count, retraction_status, source_repository, full_text_hash
- [x] 1.2.6: `ResearchContext` — research_question, domain, hypotheses_in_scope, literature_seed, constraints, ethical_flags, project_id
- [x] 1.2.7: `ReproducibilityBundle` — environment_lockfile, dependency_tree, config_snapshot, random_seeds, data_hashes, hardware_profile

### Task 1.3: Config Module

- [x] 1.3.1: `Config` model — all configurable parameters with types and defaults
- [x] 1.3.2: YAML/TOML config file parser (`openscire config init` generates default)
- [x] 1.3.3: Environment variable overrides (prefix `OPENSCIRE_`)
- [x] 1.3.4: Config validation on load (type checking, range checking, required fields)
- [x] 1.3.5: `Config.to_reproducibility_bundle()` — exports environment + dependency + config snapshot
- [x] 1.3.6: Config hierarchy: default → user config → env vars → CLI flags
- [x] 1.3.7: Secret redaction in config export (API keys masked)
- [x] 1.3.8: Config schema generation (`openscire config schema --json`)

### Task 1.4: Logging Module

- [x] 1.4.1: Structured JSON logging (`structlog` with JSON renderer)
- [x] 1.4.2: Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL + SCIENCE (custom level 25)
- [x] 1.4.3: Provenance-aware log entries (every log includes provenance_entry_id if within a research context)
- [x] 1.4.4: Configurable log output (stdout, stderr, file, syslog)
- [x] 1.4.5: Sensitive data redaction in logs (regex-matched keys replaced with REDACTED)
- [x] 1.4.6: Structured context enrichment (request_id, session_id, agent_id via LogContext)

### Task 1.5: ProvenanceTracker (Native, Not Retrofitted)

- [x] 1.5.1: `ProvenanceTracker` class — singleton per research context (`from_config()`, `get_tracker()`, `reset()`)
- [x] 1.5.2: Entry creation: `track(action_type, agent_id, model_id, params, input, output)` returns `ProvenanceEntry`
- [x] 1.5.3: Entry chaining: every entry records `parent_ids` forming a DAG; auto-chains if none specified
- [x] 1.5.4: Cryptographic signing of each entry (Ed25519) — `sign_entry()` hashes + signs via pynacl
- [x] 1.5.5: Signature verification — `verify_entry(entry, public_key)` returns `bool`
- [x] 1.5.6: Signature aggregation — `ProvenanceGraph.root_hash()` — Merkle-style bottom-up hash of topological sort
- [x] 1.5.7: `ProvenanceGraph` — DFS cycle detection on insert, `query()`, `traverse()` (bidirectional), `topological_sort()`
- [x] 1.5.8: `ProvenanceExporter` — `to_json()`, `to_ro_crate()`, `to_w3c_prov()`
- [x] 1.5.9: Storage backend abstraction — `StorageBackend` ABC; `InMemoryBackend`, `SQLiteBackend` (WAL, indexes), `PostgresBackend` (stub)
- [x] 1.5.10: `ResearchChronologyEnforcer` — `stamp_hypothesis()` timestamps via provenance; `check_evidence()` validates temporal ordering; `detect_temporal_anomalies()` returns all HARKing violations

### Task 1.6: Philosophy Foundation Models

- [x] 1.6.1: `KnowledgeBoundaryFlag` — 3-tier boundary detection (outside_corpus, unverifiable_assumptions, in_principle_unanswerable); confidence threshold; human override tracking with provenance linkage
- [x] 1.6.2: `EpistemicMarker` — SourceCategory enum (public, licensed, irb_approved, indigenous, clinical, proprietary); mandatory corpus_bias, caveats, provenance_entry_id, reasoning_trace, source_language, funding_source
- [x] 1.6.3: `FalsificationConfig` — master enabled flag; auto_generate_null_hypotheses; require_falsifiability_check; block_non_verifiable_export; promote_to_not_falsified (never "confirmed"); integrated into `Config`
- [x] 1.6.4: `AgentDiversityConfig` — serendipity_level (0–1); per-role temperature defaults (literature/hypothesis/falsification/ethics/sandbox); per-agent model provider with tool_access; fallback cascade; contradiction-driven exploration; integrated into `Config`

### Task 1.7: Exceptions Module

- [x] 1.7.1: `openSciReError` — base exception with `error_code` (ErrorCode), `message`, `source`, `timestamp`; formatted as `[ERROR_CODE] message`
- [x] 1.7.2: `ProvenanceError` — signing failure, chain break, tamper detection; defaults to `PROV_CHAIN_BREAK`
- [x] 1.7.3: `ConfigError` — invalid config, missing field, type mismatch; defaults to `CONFIG_INVALID`
- [x] 1.7.4: `ModelProviderError` — connection failure, auth failure, rate limit, unsupported capability; defaults to `MODEL_CONNECTION_FAILURE`
- [x] 1.7.5: `EthicsError` — DURC flag, sovereignty violation, indigenous data restriction; defaults to `ETHICS_DURC_FLAG`
- [x] 1.7.6: `ValidationError` — claim invalid, evidence insufficient, citation broken; defaults to `VALIDATION_CLAIM_INVALID`
- [x] 1.7.7: `ErrorCode` StrEnum in `openscire/constants.py` — 17 codes across 6 categories (ERR, PROV, CONFIG, MODEL, ETHICS, VALIDATION)
- [x] Migration: 9 existing `raise ValueError` sites in config/tracker/graph migrated to domain exceptions; `except Exception` narrowed to specific OSError types

### Task 1.8: Serialization Module

- [x] 1.8.1: JSON serialization/deserialization — `Serializer.dumps(model, "json")` / `Serializer.loads(data, ModelClass, "json")`
- [x] 1.8.2: YAML serialization — `Serializer.dumps(model, "yaml")` / `Serializer.loads(data, ModelClass, "yaml")`
- [x] 1.8.3: MessagePack — `Serializer.dumps(model, "msgpack")` / `Serializer.loads(data, ModelClass, "msgpack")`; optional dep `msgpack>=1.0` under `[perf]`
- [x] 1.8.4: Schema validation — Pydantic `model_validate` on deserialization; `SerializationError` wraps parse failures with clear messages
- [x] 1.8.5: Versioned envelope — `SerializationEnvelope` with `serialization_version`, `model_name`, `model_version`, `created_at`, `data`; forward compat via version comparison; `SchemaVersionMismatchError` for version/model mismatch

### Task 1.9: Test Framework

- [x] 1.9.1: `conftest.py` with common fixtures (config fixture, provenance tracker fixture, sample models)
- [x] 1.9.2: Base pytest structure with fixtures for model tests
- [x] 1.9.3: Unit tests for all Pydantic models (creation, validation, serialization, deserialization)
- [x] 1.9.4: Unit tests for Config module (parsing, env overrides, validation, export)
- [x] 1.9.5: Unit tests for ProvenanceTracker (entry creation, chaining, signing, verification, chronology enforcement)
- [x] 1.9.6: Unit tests for ReproducibilityBundle (export, import, compare)
- [x] 1.9.7: Unit tests for exception classes (creation, str/repr, error codes)
- [x] 1.9.8: Integration test: create config → create context → create hypothesis → provenance entry → export → verify cycle
- [x] 1.9.9: Integration test: ReproducibilityBundle export from config + environment
- [x] 1.9.10: Test coverage minimum: 90% for all modules

---

**Phase 1 Exit Criteria**: `pip install -e .` succeeds, `make test` passes with 90%+ coverage, provenance signing and verification cycle works end-to-end. Philosophy foundation models (KnowledgeBoundaryFlag, EpistemicMarker, FalsificationConfig, AgentDiversityConfig) defined and tested.
