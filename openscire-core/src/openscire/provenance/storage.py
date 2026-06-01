# SPDX-License-Identifier: Apache-2.0

"""Storage backends for provenance entries (in-memory, SQLite, Postgres stub)."""

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from openscire.models import ProvenanceEntry


class StorageBackend(ABC):
    """Abstract interface for provenance entry persistence."""

    @abstractmethod
    def save(self, entry: ProvenanceEntry) -> None: ...

    @abstractmethod
    def get(self, action_id: str) -> ProvenanceEntry | None: ...

    @abstractmethod
    def list(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> list[ProvenanceEntry]: ...

    @abstractmethod
    def delete(self, action_id: str) -> bool: ...

    @abstractmethod
    def count(self) -> int: ...


class InMemoryBackend(StorageBackend):
    """In-memory dictionary storage for provenance entries (non-persistent)."""

    def __init__(self) -> None:
        self._store: dict[str, ProvenanceEntry] = {}

    def save(self, entry: ProvenanceEntry) -> None:
        self._store[entry.action_id] = entry

    def get(self, action_id: str) -> ProvenanceEntry | None:
        return self._store.get(action_id)

    def list(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> list[ProvenanceEntry]:
        results: list[ProvenanceEntry] = []
        for entry in self._store.values():
            if agent_id is not None and entry.agent_id != agent_id:
                continue
            if action_type is not None and entry.action_type != action_type:
                continue
            if time_range is not None:
                t = entry.timestamp
                if t < time_range[0] or t > time_range[1]:
                    continue
            results.append(entry)
        return results

    def delete(self, action_id: str) -> bool:
        return self._store.pop(action_id, None) is not None

    def count(self) -> int:
        return len(self._store)


class SQLiteBackend(StorageBackend):
    """Persistent SQLite-backed storage for provenance entries."""

    def __init__(self, db_path: str | Path = "data/provenance.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS provenance_entries (
                action_id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL DEFAULT '',
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_agent
            ON provenance_entries(agent_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_type
            ON provenance_entries(action_type)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_created
            ON provenance_entries(created_at)
        """)
        self._conn.commit()

    def save(self, entry: ProvenanceEntry) -> None:
        payload = entry.model_dump_json()
        self._conn.execute(
            "INSERT OR REPLACE INTO provenance_entries "
            "(action_id, action_type, agent_id, model_id, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.action_id,
                entry.action_type,
                entry.agent_id,
                entry.model_id,
                payload,
                entry.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def get(self, action_id: str) -> ProvenanceEntry | None:
        row = self._conn.execute(
            "SELECT payload FROM provenance_entries WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            return None
        return ProvenanceEntry.model_validate_json(row[0])

    def list(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> list[ProvenanceEntry]:
        query = "SELECT payload FROM provenance_entries WHERE 1=1"
        params: list[str] = []
        if agent_id is not None:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if action_type is not None:
            query += " AND action_type = ?"
            params.append(action_type)
        if time_range is not None:
            query += " AND created_at >= ? AND created_at <= ?"
            params.append(time_range[0].isoformat())
            params.append(time_range[1].isoformat())
        rows = self._conn.execute(query, params).fetchall()
        return [ProvenanceEntry.model_validate_json(r[0]) for r in rows]

    def delete(self, action_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM provenance_entries WHERE action_id = ?",
            (action_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM provenance_entries").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()


class PostgresBackend(StorageBackend):
    def __init__(self) -> None:
        msg = (
            "PostgreSQL backend is planned for Phase 4. "
            "Use InMemoryBackend or SQLiteBackend for now."
        )
        raise NotImplementedError(msg)

    def save(self, entry: ProvenanceEntry) -> None:
        raise NotImplementedError

    def get(self, action_id: str) -> ProvenanceEntry | None:
        raise NotImplementedError

    def list(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> list[ProvenanceEntry]:
        raise NotImplementedError

    def delete(self, action_id: str) -> bool:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError
