from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from openscire.references.retraction.models import (
    RetractionRecord,
    RetractionSource,
    RetractionStatus,
)


class RetractionDatabase:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self) -> None:
        assert self._conn is not None
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS retraction_records (
                identifier TEXT NOT NULL,
                source TEXT NOT NULL,
                retraction_status TEXT NOT NULL DEFAULT 'unchecked',
                detected_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                notice_text TEXT DEFAULT '',
                notice_url TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                details TEXT DEFAULT '{}',
                PRIMARY KEY (identifier, source)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_retraction_status
            ON retraction_records(retraction_status)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_retraction_updated
            ON retraction_records(updated_at)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_retraction_source
            ON retraction_records(source)
        """)
        self._conn.commit()

    def upsert(self, record: RetractionRecord) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO retraction_records
                (identifier, source, retraction_status, detected_at, updated_at,
                 notice_text, notice_url, reason, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(identifier, source) DO UPDATE SET
                retraction_status = excluded.retraction_status,
                updated_at = excluded.updated_at,
                notice_text = excluded.notice_text,
                notice_url = excluded.notice_url,
                reason = excluded.reason,
                details = excluded.details
            """,
            (
                record.identifier,
                record.source.value,
                record.retraction_status.value,
                record.detected_at.isoformat(),
                record.updated_at.isoformat(),
                record.notice_text,
                record.notice_url,
                record.reason,
                json.dumps(record.details),
            ),
        )
        conn.commit()

    def get(
        self,
        identifier: str,
        source: RetractionSource | None = None,
    ) -> RetractionRecord | None:
        conn = self._get_conn()
        if source:
            row = conn.execute(
                "SELECT * FROM retraction_records WHERE identifier = ? AND source = ?",
                (identifier, source.value),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM retraction_records WHERE identifier = ?",
                (identifier,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_retracted(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RetractionRecord]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM retraction_records "
            "WHERE retraction_status IN ('retracted', 'expression_of_concern') "
            "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_needing_update(
        self,
        max_age_seconds: int = 86400,
        limit: int = 500,
    ) -> list[RetractionRecord]:
        conn = self._get_conn()
        cutoff = (datetime.now(UTC) - timedelta(seconds=max_age_seconds)).isoformat()
        rows = conn.execute(
            "SELECT * FROM retraction_records "
            "WHERE updated_at < ? "
            "ORDER BY updated_at ASC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_all_identifiers(self) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT identifier FROM retraction_records"
        ).fetchall()
        return [r["identifier"] for r in rows]

    def count(self) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM retraction_records"
        ).fetchone()
        return int(row[0]) if row else 0

    def count_by_status(self, status: RetractionStatus) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM retraction_records WHERE retraction_status = ?",
            (status.value,),
        ).fetchone()
        return int(row[0]) if row else 0

    def delete(self, identifier: str, source: RetractionSource) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM retraction_records WHERE identifier = ? AND source = ?",
            (identifier, source.value),
        )
        conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _row_to_record(self, row: sqlite3.Row) -> RetractionRecord:
        return RetractionRecord(
            identifier=row["identifier"],
            source=RetractionSource(row["source"]),
            retraction_status=RetractionStatus(row["retraction_status"]),
            detected_at=datetime.fromisoformat(row["detected_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            notice_text=row["notice_text"] or "",
            notice_url=row["notice_url"] or "",
            reason=row["reason"] or "",
            details=json.loads(row["details"] or "{}"),
        )
