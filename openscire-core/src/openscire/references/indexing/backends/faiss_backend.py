from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from openscire.references.indexing.backends import VectorBackend

logger = logging.getLogger(__name__)


class FaissBackend(VectorBackend):
    def __init__(self, dimension: int = 768) -> None:
        self._dimension = dimension
        self._index = None
        self._metadata: dict[str, dict[str, Any]] = {}
        self._next_id: int = 0
        self._id_map: dict[str, int] = {}
        self._rev_id_map: dict[int, str] = {}

    def _ensure_index(self) -> Any:  # noqa: ANN401
        if self._index is not None:
            return self._index
        try:
            import faiss
            self._index = faiss.IndexIDMap(faiss.IndexFlatIP(self._dimension))
            return self._index
        except ImportError:
            raise ImportError(
                "faiss is required for FaissBackend. "
                "Install with: pip install openscire-core[indexing]"
            ) from None

    def add(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        import numpy as np
        index = self._ensure_index()
        if not ids:
            return
        import faiss
        vec_array = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(vec_array)
        int_ids = []
        for i, doc_id in enumerate(ids):
            if doc_id in self._id_map:
                int_id = self._id_map[doc_id]
            else:
                int_id = self._next_id
                self._next_id += 1
                self._id_map[doc_id] = int_id
                self._rev_id_map[int_id] = doc_id
            int_ids.append(int_id)
            if metadatas:
                self._metadata[doc_id] = metadatas[i]
            else:
                self._metadata.setdefault(doc_id, {})
        id_array = np.array(int_ids, dtype=np.int64)
        index.add_with_ids(vec_array, id_array)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        import numpy as np
        index = self._ensure_index()
        n_total = index.ntotal
        if n_total == 0:
            return []
        k = min(top_k, n_total)
        vec = np.array([query_vector], dtype=np.float32)
        import faiss
        faiss.normalize_L2(vec)
        scores, ids = index.search(vec, k)
        results: list[tuple[str, float, dict[str, Any]]] = []
        for i in range(k):
            int_id = ids[0][i]
            if int_id == -1:
                break
            doc_id = self._rev_id_map.get(int(int_id), str(int_id))
            score = float(scores[0][i])
            meta = self._metadata.get(doc_id, {})
            results.append((doc_id, score, meta))
        return results

    def delete(self, ids: list[str]) -> None:
        import faiss
        index = self._ensure_index()
        int_ids = [self._id_map[doc_id] for doc_id in ids if doc_id in self._id_map]
        if not int_ids:
            return
        import numpy as np
        id_array = np.array(int_ids, dtype=np.int64)
        index.remove_ids(id_array)
        for doc_id in ids:
            self._metadata.pop(doc_id, None)
            int_id = self._id_map.pop(doc_id, None)
            if int_id is not None:
                self._rev_id_map.pop(int_id, None)

    def count(self) -> int:
        if self._index is None:
            return 0
        return self._index.ntotal

    def save(self, path: str) -> None:
        import faiss
        index = self._ensure_index()
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(p / "index.faiss"))
        meta = {
            "metadata": self._metadata,
            "id_map": self._id_map,
            "rev_id_map": {str(k): v for k, v in self._rev_id_map.items()},
            "next_id": self._next_id,
            "dimension": self._dimension,
        }
        with open(p / "metadata.json", "w") as f:
            json.dump(meta, f, indent=2, default=str)

    def load(self, path: str) -> None:
        import faiss
        p = Path(path)
        index_path = p / "index.faiss"
        meta_path = p / "metadata.json"
        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Index not found at {path}")
        self._index = faiss.read_index(str(index_path))
        self._dimension = self._index.d
        with open(meta_path) as f:
            meta = json.load(f)
        self._metadata = meta["metadata"]
        self._id_map = meta["id_map"]
        self._rev_id_map = {int(k): v for k, v in meta["rev_id_map"].items()}
        self._next_id = meta["next_id"]

    def clear(self) -> None:
        self._index = None
        self._metadata.clear()
        self._id_map.clear()
        self._rev_id_map.clear()
        self._next_id = 0
