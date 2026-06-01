# SPDX-License-Identifier: Apache-2.0

"""Provenance tracking and verification for openSciRe.

Provides immutable audit trails, cryptographic entry signing, chronology
enforcement, and configurable storage backends (in-memory, SQLite, Postgres).
"""

from .enforcer import ResearchChronologyEnforcer
from .entry import content_hash, sign_entry, verify_entry
from .exporter import ProvenanceExporter
from .graph import ProvenanceGraph
from .storage import (
    InMemoryBackend,
    PostgresBackend,
    SQLiteBackend,
    StorageBackend,
)
from .tracker import ProvenanceTracker

__all__ = [
    "ProvenanceTracker",
    "ProvenanceGraph",
    "ProvenanceExporter",
    "ResearchChronologyEnforcer",
    "StorageBackend",
    "InMemoryBackend",
    "SQLiteBackend",
    "PostgresBackend",
    "content_hash",
    "sign_entry",
    "verify_entry",
]
