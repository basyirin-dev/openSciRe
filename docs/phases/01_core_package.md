# Phase 1 — Core Python Package (Provenance-Native)

**Duration**: 3 weeks (Jul 2026)
**Dependencies**: Phase 0, Phase 0.5 (go decision)
**Output**: Installable `skepsis-core` package with provenance-native architecture

---

### Task 1.1: Package Directory Structure

- [ ] 1.1.1: Create `skepsis-core/` at project root
- [ ] 1.1.2: Create `skepsis-core/src/skepsis/__init__.py` with version string
- [ ] 1.1.3: Create subpackage directories: `models/`, `config/`, `provenance/`, `logging/`, `exceptions/`, `serialization/`
- [ ] 1.1.4: Create `__init__.py` in each subpackage
- [ ] 1.1.5: Create `skepsis-core/tests/` with `__init__.py` and `conftest.py`
- [ ] 1.1.6: Create `skepsis-core/tests/unit/` and `skepsis-core/tests/integration/`
- [ ] 1.1.7: Verify `pip install -e ./skepsis-core` works and `import skepsis` succeeds

### Task 1.2: Base Pydantic Models

- [ ] 1.2.1: `ScientificClaim` — field, evidence_chain, confidence_interval, source_references, verification_status, timestamp, created_by
- [ ] 1.2.2: `Evidence` — type (experimental, computational, literature, anecdotal), source, strength_rating, reproducibility_status, date_collected
- [ ] 1.2.3: `Hypothesis` — claim, null_hypothesis, falsification_criteria, testability_score, domain_tags, related_literature, status (proposed, tested, supported, refuted)
- [ ] 1.2.4: `ProvenanceEntry` — action_id, parent_ids, agent_id, model_id, parameters_snapshot, input_hash, output_hash, timestamp, cryptographic_signature
- [ ] 1.2.5: `LiteratureReference` — doi, title, authors, journal, year, citation_count, retraction_status, source_repository, full_text_hash
- [ ] 1.2.6: `ResearchContext` — research_question, domain, hypotheses_in_scope, literature_seed, constraints, ethical_flags, project_id
- [ ] 1.2.7: `ReproducibilityBundle` — environment_lockfile, dependency_tree, config_snapshot, random_seeds, data_hashes, hardware_profile

### Task 1.3: Config Module

- [ ] 1.3.1: `Config` model — all configurable parameters with types and defaults
- [ ] 1.3.2: YAML/TOML config file parser (`skepsis config init` generates default)
- [ ] 1.3.3: Environment variable overrides (prefix `SKEPSIS_`)
- [ ] 1.3.4: Config validation on load (type checking, range checking, required fields)
- [ ] 1.3.5: `Config.to_reproducibility_bundle()` — exports environment + dependency + config snapshot
- [ ] 1.3.6: Config hierarchy: default → user config → env vars → CLI flags
- [ ] 1.3.7: Secret redaction in config export (API keys masked)
- [ ] 1.3.8: Config schema generation (`skepsis config schema --json`)

### Task 1.4: Logging Module

- [ ] 1.4.1: Structured JSON logging (`structlog` or standard `logging` with JSON formatter)
- [ ] 1.4.2: Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL + SCIENCE (custom level for research-relevant events)
- [ ] 1.4.3: Provenance-aware log entries (every log includes provenance_entry_id if within a research context)
- [ ] 1.4.4: Configurable log output (stdout, file, syslog)
- [ ] 1.4.5: Sensitive data redaction in logs (API keys, file paths, user queries)
- [ ] 1.4.6: Structured context enrichment (request_id, session_id, agent_id)

### Task 1.5: ProvenanceTracker (Native, Not Retrofitted)

- [ ] 1.5.1: `ProvenanceTracker` class — singleton per research context
- [ ] 1.5.2: Entry creation: `track(action_type, agent_id, model_id, params, input, output)` returns `ProvenanceEntry`
- [ ] 1.5.3: Entry chaining: every entry records `parent_ids` forming a DAG
- [ ] 1.5.4: Cryptographic signing of each entry (Ed25519) — entry contents hash signed with project key
- [ ] 1.5.5: Signature verification method — `provenance_entry.verify()` returns `bool`
- [ ] 1.5.6: Signature aggregation — root hash of DAG for audit report
- [ ] 1.5.7: `ProvenanceGraph` — traversal, query by agent, by time range, by action type
- [ ] 1.5.8: `ProvenanceExporter` — export to JSON, RO-Crate, W3C PROV
- [ ] 1.5.9: Storage backend abstraction — in-memory (dev), SQLite (local), PostgreSQL (server)
- [ ] 1.5.10: `ResearchChronologyEnforcer` — cryptographically timestamps hypotheses before evidence synthesis; detects temporal ordering violations (HARKing detection)

### Task 1.6: Exceptions Module

- [ ] 1.6.1: `SkepsisError` — base exception with error code, message, source, timestamp
- [ ] 1.6.2: `ProvenanceError` — signing failure, chain break, tamper detection
- [ ] 1.6.3: `ConfigError` — invalid config, missing required field, type mismatch
- [ ] 1.6.4: `ModelProviderError` — connection failure, auth failure, rate limit, unsupported capability
- [ ] 1.6.5: `EthicsError` — DURC flag, sovereignty violation, indigenous data restriction
- [ ] 1.6.6: `ValidationError` — claim invalid, evidence insufficient, citation broken
- [ ] 1.6.7: Error codes enumerated in `skepsis/constants.py`

### Task 1.7: Serialization Module

- [ ] 1.7.1: JSON serialization/deserialization for all Pydantic models
- [ ] 1.7.2: YAML serialization for config output
- [ ] 1.7.3: MessagePack for performance-critical internal transport
- [ ] 1.7.4: Schema validation on deserialization (reject malformed input)
- [ ] 1.7.5: Versioned serialization format (allow forward/backward compatibility)

### Task 1.8: Test Framework

- [ ] 1.8.1: `conftest.py` with common fixtures (config fixture, provenance tracker fixture, sample models)
- [ ] 1.8.2: Base test class for model tests
- [ ] 1.8.3: Unit tests for all Pydantic models (creation, validation, serialization, deserialization)
- [ ] 1.8.4: Unit tests for Config module (parsing, env overrides, validation, export)
- [ ] 1.8.5: Unit tests for ProvenanceTracker (entry creation, chaining, signing, verification, chronology enforcement)
- [ ] 1.8.6: Unit tests for ReproducibilityBundle (export, import, compare)
- [ ] 1.8.7: Unit tests for exception classes (creation, str/repr, error codes)
- [ ] 1.8.8: Integration test: create config → create context → create hypothesis → provenance entry → export → verify cycle
- [ ] 1.8.9: Integration test: ReproducibilityBundle export from config + environment
- [ ] 1.8.10: Test coverage minimum: 90% for all modules

---

**Phase 1 Exit Criteria**: `pip install -e .` succeeds, `make test` passes with 90%+ coverage, provenance signing and verification cycle works end-to-end.
