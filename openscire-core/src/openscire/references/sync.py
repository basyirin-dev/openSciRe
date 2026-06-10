# SPDX-License-Identifier: Apache-2.0

"""Incremental sync state management for reference manager bridges.

Sync state is persisted to a JSON file. Each bridge (e.g., Zotero user,
Mendeley account) has its own entry keyed by ``(source, bridge_id)``.
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from openscire.logging import get_logger
from openscire.references.models import ReferenceSource, SyncState

logger = get_logger("openscire.references.sync")


class SyncManager:
    """Persist and retrieve incremental sync state for reference bridges.

    State is stored in a JSON file on disk. Thread-safe for single-process use.

    Args:
        storage_path: Path to the JSON state file.
    """

    def __init__(self, storage_path: str | Path = "data/sync_state.json") -> None:
        self._path = Path(storage_path)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt sync state file, starting fresh")
            return {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    @staticmethod
    def _key(source: ReferenceSource, bridge_id: str) -> str:
        return f"{source.value}:{bridge_id}"

    def get_sync_state(self, source: ReferenceSource, bridge_id: str) -> SyncState | None:
        """Retrieve the last sync state for a bridge.

        Args:
            source: The reference source (Zotero, Mendeley, etc.).
            bridge_id: Unique identifier (e.g., Zotero user ID, profile name).

        Returns:
            SyncState if previously synced, None otherwise.
        """
        data = self._load()
        key = self._key(source, bridge_id)
        entry = data.get(key)
        if entry is None:
            return None

        last_sync_str = entry.get("last_sync")
        last_sync: datetime | None = None
        if last_sync_str:
            with contextlib.suppress(ValueError, TypeError):
                last_sync = datetime.fromisoformat(str(last_sync_str))

        return SyncState(
            source=source,
            bridge_id=bridge_id,
            last_sync=last_sync,
            last_version=int(entry.get("last_version", 0)),
            sync_token=str(entry.get("sync_token", "")),
        )

    def set_sync_state(self, state: SyncState) -> None:
        """Persist updated sync state for a bridge.

        Args:
            state: The new sync state to persist.
        """
        data = self._load()
        key = self._key(state.source, state.bridge_id)
        data[key] = {
            "last_sync": state.last_sync.isoformat() if state.last_sync else None,
            "last_version": state.last_version,
            "sync_token": state.sync_token,
        }
        self._save(data)
        logger.debug(
            "Saved sync state for %s/%s (version=%d)",
            state.source.value,
            state.bridge_id,
            state.last_version,
        )

    def clear_sync_state(self, source: ReferenceSource, bridge_id: str) -> None:
        """Remove the sync state entry for a bridge.

        Args:
            source: The reference source.
            bridge_id: Unique identifier for the bridge instance.
        """
        data = self._load()
        key = self._key(source, bridge_id)
        data.pop(key, None)
        self._save(data)
        logger.info(
            "Cleared sync state for %s/%s",
            source.value,
            bridge_id,
        )
