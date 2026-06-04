from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from openscire.references.indexing.backends import VectorBackend

logger = logging.getLogger(__name__)


class LocalBackend(VectorBackend):
    def __init__(self, dimension: int = 768) -> None:
        self._dimension = dimension
        self._vectors: list[list[float]] = []
        self._ids: list[str] = []
        self._metadata: dict[str, dict[str, Any]] = {}
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(":memory:")
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    def add(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if not ids:
            return
        import struct
        conn = self._get_conn()
        for i, doc_id in enumerate(ids):
            vec_bytes = struct.pack(f"{len(vectors[i])}f", *vectors[i])
            meta_json = json.dumps(metadatas[i] if metadatas else {}, default=str)
            conn.execute(
                "INSERT OR REPLACE INTO vectors (id, vector, metadata) VALUES (?, ?, ?)",
                (doc_id, vec_bytes, meta_json),
            )
            if doc_id not in self._id_set():
                self._ids.append(doc_id)
                self._vectors.append(vectors[i])
                self._metadata[doc_id] = metadatas[i] if metadatas else {}
            else:
                idx = self._ids.index(doc_id)
                self._vectors[idx] = vectors[i]
                self._metadata[doc_id] = metadatas[i] if metadatas else {}
        conn.commit()

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        if not self._vectors:
            return []
        import numpy as np
        query = np.array(query_vector, dtype=np.float32)
        query = query / (np.linalg.norm(query) + 1e-10)
        matrix = np.array(self._vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
        matrix = matrix / norms
        scores = np.dot(matrix, query)
        top_indices = np.argsort(scores)[::-1][:top_k]
        results: list[tuple[str, float, dict[str, Any]]] = []
        for idx in top_indices:
            doc_id = self._ids[int(idx)]
            score = float(scores[int(idx)])
            meta = self._metadata.get(doc_id, {})
            results.append((doc_id, score, meta))
        return results

    def delete(self, ids: list[str]) -> None:
        conn = self._get_conn()
        id_set = set(ids)
        self._ids = [i for i in self._ids if i not in id_set]
        self._vectors = [
            v for i, v in zip(self._ids, self._vectors, strict=False)
            if i not in id_set
        ]
        for doc_id in ids:
            self._metadata.pop(doc_id, None)
            conn.execute("DELETE FROM vectors WHERE id = ?", (doc_id,))
        conn.commit()

    def count(self) -> int:
        return len(self._ids)

    def save(self, path: str) -> None:
        import struct
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        backup = sqlite3.connect(str(p / "index.db"))
        conn.backup(backup)
        backup.close()
        with open(p / "metadata.json", "w") as f:
            json.dump({
                "dimension": self._dimension,
                "ids": self._ids,
            }, f, indent=2)

    def load(self, path: str) -> None:
        import struct
        p = Path(path)
        db_path = p / "index.db"
        meta_path = p / "metadata.json"
        if not db_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Index not found at {path}")
        with open(meta_path) as f:
            meta = json.load(f)
        self._dimension = meta.get("dimension", 768)
        backup = sqlite3.connect(str(db_path))
        conn = self._get_conn()
        backup.backup(conn)
        backup.close()
        rows = conn.execute("SELECT id, vector, metadata FROM vectors").fetchall()
        import struct
        self._ids = []
        self._vectors = []
        self._metadata = {}
        for row in rows:
            doc_id = row["id"]
            vec_bytes = row["vector"]
            n_floats = len(vec_bytes) // 4
            vec = list(struct.unpack(f"{n_floats}f", vec_bytes))
            self._ids.append(doc_id)
            self._vectors.append(vec)
            self._metadata[doc_id] = json.loads(row["metadata"])

    def clear(self) -> None:
        self._vectors.clear()
        self._ids.clear()
        self._metadata.clear()
        if self._conn is not None:
            self._conn.execute("DELETE FROM vectors")
            self._conn.commit()

    def _id_set(self) -> set[str]:
        return set(self._ids)
