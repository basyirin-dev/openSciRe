# SPDX-License-Identifier: Apache-2.0

"""Cross-link negative results to related literature references.

Uses a dedicated junction table (``negative_result_cross_links``)
stored in the same SQLite database as the main :class:`RegistryStore`.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from typing import Any

from openscire.negative_results.models import NegativeResult
from openscire.negative_results.store import RegistryStore

logger = logging.getLogger(__name__)

_JUNCTION_SQL = """
CREATE TABLE IF NOT EXISTS negative_result_cross_links (
    result_id    TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    relationship TEXT    DEFAULT 'related',
    created_at   TEXT    NOT NULL,
    PRIMARY KEY (result_id, reference_id)
)
"""

_JUNCTION_IDX = """
CREATE INDEX IF NOT EXISTS nrcl_reference
    ON negative_result_cross_links(reference_id)
"""


class NegativeResultCrossLinker:
    """Connect negative results to related literature references.

    Requires a :class:`RegistryStore` whose connection is already open.
    The cross-link table is created alongside the main store table on
    first use.
    """

    def __init__(
        self,
        store: RegistryStore,
        openalex_client: Any = None,  # noqa: ANN401
    ) -> None:
        self._store = store
        self._openalex = openalex_client

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_table(self) -> None:
        conn = self._require_conn()
        conn.execute(_JUNCTION_SQL)
        conn.execute(_JUNCTION_IDX)
        conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def link_to_reference(
        self,
        result_id: str,
        reference_id: str,
        relationship: str = "related",
    ) -> bool:
        """Create a link between a negative result and a reference.

        Returns ``True`` if the link was created, ``False`` if it
        already existed.
        """
        self._ensure_table()
        conn = self._require_conn()
        try:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO negative_result_cross_links
                   (result_id, reference_id, relationship, created_at)
                   VALUES (?, ?, ?, ?)""",
                (result_id, reference_id, relationship, datetime.now(UTC).isoformat()),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            logger.warning(
                "Cross-link FK violation: result_id=%s reference_id=%s",
                result_id,
                reference_id,
            )
            return False

    def unlink_reference(self, result_id: str, reference_id: str) -> bool:
        """Remove a specific cross-link."""
        self._ensure_table()
        conn = self._require_conn()
        cursor = conn.execute(
            "DELETE FROM negative_result_cross_links WHERE result_id = ? AND reference_id = ?",
            (result_id, reference_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_links(self, result_id: str) -> list[dict[str, Any]]:
        """Return all cross-links for a given result."""
        self._ensure_table()
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT reference_id, relationship, created_at"
            " FROM negative_result_cross_links WHERE result_id = ?"
            " ORDER BY created_at DESC",
            (result_id,),
        ).fetchall()
        return [
            {
                "reference_id": r[0],
                "relationship": r[1],
                "created_at": r[2],
            }
            for r in rows
        ]

    def find_referencing_results(self, reference_id: str) -> list[NegativeResult]:
        """Find all negative results that cite a specific reference."""
        self._ensure_table()
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT nr.* FROM negative_results nr"
            " JOIN negative_result_cross_links cl ON nr.result_id = cl.result_id"
            " WHERE cl.reference_id = ?"
            " ORDER BY nr.created_at DESC",
            (reference_id,),
        ).fetchall()
        from openscire.negative_results.store import _from_row

        return [_from_row(r) for r in rows]

    def find_related_references(
        self,
        result: NegativeResult,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Find literature references related to this result.

        Uses the optional OpenAlex client for similarity search.
        Falls back to empty list if no client is available.
        """
        if self._openalex is None:
            return []

        try:
            results: list[dict[str, Any]] = []
            seen: set[str] = set()

            if hasattr(self._openalex, "search"):
                for response in self._openalex.search(
                    result.hypothesis,
                    max_results=max_results,
                ):
                    ref_id = response.get("id", "")
                    if ref_id and ref_id not in seen:
                        seen.add(ref_id)
                        results.append(
                            {
                                "source_id": ref_id,
                                "title": response.get("title", ""),
                                "url": response.get("url", ""),
                                "relevance_score": response.get(
                                    "relevance_score",
                                    0.0,
                                ),
                            }
                        )
            return results[:max_results]
        except Exception as exc:
            logger.warning("OpenAlex search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def get_all_links(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return all cross-links paginated."""
        self._ensure_table()
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT result_id, reference_id, relationship, created_at"
            " FROM negative_result_cross_links"
            " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            {
                "result_id": r[0],
                "reference_id": r[1],
                "relationship": r[2],
                "created_at": r[3],
            }
            for r in rows
        ]

    def count_links(self) -> int:
        """Total number of cross-links."""
        self._ensure_table()
        conn = self._require_conn()
        return conn.execute(
            "SELECT COUNT(*) FROM negative_result_cross_links",
        ).fetchone()[0]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_conn(self) -> sqlite3.Connection:
        if not self._store.connected:
            raise RuntimeError("RegistryStore must be connected first")
        return self._store._require_conn()  # noqa: SLF001
