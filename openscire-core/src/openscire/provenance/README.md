# openSciRe — Provenance

Purpose: Full-provenance tracking for all research artifacts using a DAG structure with cryptographic signing (Ed25519), pluggable storage backends, and RO-Crate / W3C PROV export.

Status: Stable

Public API:
- `ProvenanceTracker` — High-level API for recording operations, maintaining chronology, and computing diffs between states
- `ProvenanceGraph` — Directed acyclic graph of provenance entries with cycle detection, topological sort, and subgraph queries
- `ProvenanceExporter` — Exports provenance graphs to JSON, RO-Crate (JSON-LD), and W3C PROV-N formats
- `ResearchChronologyEnforcer` — Enforces causal ordering: entries must reference valid predecessors, rejects out-of-order timestamps
- `StorageBackend` — Abstract base class for provenance storage
- `InMemoryBackend` — In-memory dict-based storage (testing, ephemeral sessions)
- `SQLiteBackend` — Persistent SQLite-backed storage with indexing and query support
- `PostgresBackend` — PostgreSQL-backed storage for production multi-user deployments
- `content_hash` — Deterministic SHA-256 hash of serialized model content
- `sign_entry` — Ed25519-sign a provenance entry given a private key (bytes or nacl signing key)
- `verify_entry` — Verify a provenance entry's Ed25519 signature against a public key
