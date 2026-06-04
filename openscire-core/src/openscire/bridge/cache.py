# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
import pickle
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class CacheTTL(BaseModel):
    search: int = 300
    get: int = 3600
    metadata: int = 86400


class CacheLayer:
    def __init__(
        self,
        db_path: str = "data/bridge_cache.db",
        ttls: dict[str, int] | None = None,
    ) -> None:
        self.db_path = db_path
        self._ttls = CacheTTL(**(ttls or {}))
        self._local = threading.local()
        self._ensure_db()

    def _ensure_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bridge_cache (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    def _make_key(self, bridge_name: str, endpoint: str, params: dict[str, Any]) -> str:
        raw = f"{bridge_name}:{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, key: str) -> Any | None:  # noqa: ANN401
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT value, expires_at FROM bridge_cache WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        value_blob, expires_at = row
        if time.time() >= expires_at:
            conn.execute("DELETE FROM bridge_cache WHERE key = ?", (key,))
            conn.commit()
            return None
        return pickle.loads(value_blob)

    async def set(
        self,
        key: str,
        value: Any,  # noqa: ANN401
        ttl: int | None = None,
    ) -> None:
        effective_ttl = ttl if ttl is not None else 3600
        expires_at = time.time() + effective_ttl
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO bridge_cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, pickle.dumps(value), expires_at),
        )
        conn.commit()

    async def clear(self) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM bridge_cache")
        conn.commit()
