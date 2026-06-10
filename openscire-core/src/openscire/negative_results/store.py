# SPDX-License-Identifier: Apache-2.0

"""SQLite-backed persistent storage for the Negative Result Registry."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from openscire.negative_results.models import (
    NegativeResult,
    NegativeResultQuery,
)

logger = logging.getLogger(__name__)

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS negative_results (
    result_id        TEXT PRIMARY KEY,
    hypothesis       TEXT NOT NULL,
    method_used      TEXT DEFAULT '',
    data_summary     TEXT DEFAULT '',
    outcome          TEXT NOT NULL,
    confidence       REAL DEFAULT 0.0,
    reason_for_failure TEXT DEFAULT '',
    suggestions      TEXT DEFAULT '[]',
    source_references TEXT DEFAULT '[]',
    domain_tags      TEXT DEFAULT '[]',
    created_at       TEXT NOT NULL,
    created_by       TEXT DEFAULT '',
    ttl_days         INTEGER DEFAULT 365,
    expires_at       TEXT,
    provenance_entry_id TEXT
)
"""

_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS nr_outcome ON negative_results(outcome)",
    "CREATE INDEX IF NOT EXISTS nr_created_at ON negative_results(created_at)",
    "CREATE INDEX IF NOT EXISTS nr_expires_at ON negative_results(expires_at)",
    "CREATE INDEX IF NOT EXISTS nr_created_by ON negative_results(created_by)",
]


class RegistryStore:
    """SQLite-backed persistent store for negative results.

    Thread-safe via ``check_same_thread=False``.  All datetime values
    are stored as ISO-8601 UTC strings.  List fields are stored as
    JSON text arrays and are transparently deserialised by
    :class:`NegativeResult`'s ``model_validator``.
    """

    def __init__(self, db_path: str | Path = "data/negative_results.db") -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open (or re-open) the database connection."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()
        logger.info("RegistryStore connected: %s", self._db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("RegistryStore closed")

    @property
    def connected(self) -> bool:
        return self._conn is not None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_tables(self) -> None:
        conn = self._require_conn()
        conn.execute(_TABLE_SQL)
        for idx in _INDEXES_SQL:
            conn.execute(idx)
        conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def submit(self, result: NegativeResult) -> str:
        """Insert *result* into the store and return its ``result_id``.

        If ``expires_at`` is not set, it is computed from
        ``created_at + ttl_days``.
        """
        conn = self._require_conn()

        if result.expires_at is None:
            result.expires_at = result.created_at + timedelta(
                days=result.ttl_days,
            )

        row = _to_row(result)
        conn.execute(
            """INSERT OR REPLACE INTO negative_results (
                result_id, hypothesis, method_used, data_summary,
                outcome, confidence, reason_for_failure,
                suggestions, source_references, domain_tags,
                created_at, created_by, ttl_days, expires_at,
                provenance_entry_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            row,
        )
        conn.commit()
        return result.result_id

    def get(self, result_id: str) -> NegativeResult | None:
        """Retrieve a single result by ID."""
        conn = self._require_conn()
        row = conn.execute(
            "SELECT * FROM negative_results WHERE result_id = ?",
            (result_id,),
        ).fetchone()
        if row is None:
            return None
        return _from_row(row)

    def list_all(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NegativeResult]:
        """Return recent results in reverse chronological order."""
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT * FROM negative_results ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_from_row(r) for r in rows]

    def count(self) -> int:
        """Return the total number of stored results."""
        conn = self._require_conn()
        return conn.execute(
            "SELECT COUNT(*) FROM negative_results",
        ).fetchone()[0]

    def delete(self, result_id: str) -> bool:
        """Delete a result by ID.  Returns ``True`` if something was deleted."""
        conn = self._require_conn()
        cursor = conn.execute(
            "DELETE FROM negative_results WHERE result_id = ?",
            (result_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: NegativeResultQuery) -> list[NegativeResult]:
        """Search results matching the given *query*.

        Builds a dynamic WHERE clause from non-``None`` fields.
        """
        conn = self._require_conn()

        clauses: list[str] = []
        params: list[Any] = []

        if query.domain:
            clauses.append("domain_tags LIKE ?")
            params.append(f'%"{query.domain}"%')
        if query.topic:
            clauses.append("hypothesis LIKE ?")
            params.append(f"%{query.topic}%")
        if query.method:
            clauses.append("method_used LIKE ?")
            params.append(f"%{query.method}%")
        if query.outcome:
            clauses.append("outcome = ?")
            params.append(query.outcome.value)
        if query.date_from is not None:
            clauses.append("created_at >= ?")
            params.append(query.date_from.isoformat())
        if query.date_to is not None:
            clauses.append("created_at <= ?")
            params.append(query.date_to.isoformat())
        if query.created_by:
            clauses.append("created_by = ?")
            params.append(query.created_by)

        where = " AND ".join(clauses) if clauses else "1"

        sql = (
            f"SELECT * FROM negative_results WHERE {where}"
            " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([query.limit, query.offset])

        rows = conn.execute(sql, params).fetchall()
        return [_from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def purge_expired(self) -> int:
        """Delete all entries whose ``expires_at`` is in the past.

        Returns the number of deleted rows.
        """
        now = datetime.now(UTC).isoformat()
        conn = self._require_conn()
        cursor = conn.execute(
            "DELETE FROM negative_results WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        conn.commit()
        count = cursor.rowcount
        if count:
            logger.info("Purged %d expired negative result(s)", count)
        return count

    def get_graveyard_stats(self) -> dict[str, Any]:
        """Aggregate statistics for the 'graveyard' visualisation."""
        conn = self._require_conn()

        total = conn.execute(
            "SELECT COUNT(*) FROM negative_results",
        ).fetchone()[0]

        by_outcome: dict[str, int] = {}
        for row in conn.execute(
            "SELECT outcome, COUNT(*) FROM negative_results GROUP BY outcome",
        ).fetchall():
            by_outcome[row[0]] = row[1]

        by_domain: dict[str, int] = {}
        for (tags_str,) in conn.execute(
            "SELECT domain_tags FROM negative_results",
        ).fetchall():
            for tag in json.loads(tags_str if tags_str else "[]"):
                by_domain[tag] = by_domain.get(tag, 0) + 1

        now_iso = datetime.now(UTC).isoformat()
        expired = conn.execute(
            "SELECT COUNT(*) FROM negative_results WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now_iso,),
        ).fetchone()[0]

        return {
            "total": total,
            "active": total - expired,
            "expired": expired,
            "by_outcome": by_outcome,
            "by_domain": by_domain,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError(
                "RegistryStore is not connected. Call .connect() first.",
            )
        return self._conn


# ------------------------------------------------------------------
# Row mapping helpers
# ------------------------------------------------------------------


def _to_row(result: NegativeResult) -> tuple[Any, ...]:
    """Convert a NegativeResult to a parameters tuple for INSERT."""
    return (
        result.result_id,
        result.hypothesis,
        result.method_used,
        result.data_summary,
        result.outcome.value,
        result.confidence,
        result.reason_for_failure,
        json.dumps(result.suggestions),
        json.dumps(result.source_references),
        json.dumps(result.domain_tags),
        result.created_at.isoformat(),
        result.created_by,
        result.ttl_days,
        result.expires_at.isoformat() if result.expires_at else None,
        result.provenance_entry_id,
    )


def _from_row(row: sqlite3.Row | tuple) -> NegativeResult:
    """Reconstruct a NegativeResult from a raw SQLite row.

    Handles both ``sqlite3.Row`` objects and plain tuples so the
    function works regardless of connection row factory.
    """
    if isinstance(row, sqlite3.Row):
        keys = row.keys()
        data = {keys[i]: row[i] for i in range(len(keys))}
    else:
        data = {
            "result_id": row[0],
            "hypothesis": row[1],
            "method_used": row[2],
            "data_summary": row[3],
            "outcome": row[4],
            "confidence": row[5],
            "reason_for_failure": row[6],
            "suggestions": row[7],
            "source_references": row[8],
            "domain_tags": row[9],
            "created_at": row[10],
            "created_by": row[11],
            "ttl_days": row[12],
            "expires_at": row[13],
            "provenance_entry_id": row[14],
        }
    return NegativeResult.model_validate(data)
