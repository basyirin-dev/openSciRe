# SPDX-License-Identifier: Apache-2.0

"""Singleton-per-project tracker that records, signs, and indexes provenance entries."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from openscire.config import Config
from openscire.constants import ErrorCode
from openscire.exceptions import ConfigError
from openscire.logging import get_logger
from openscire.models import ProvenanceEntry

from .entry import sign_entry
from .graph import ProvenanceGraph
from .storage import (
    InMemoryBackend,
    PostgresBackend,
    SQLiteBackend,
    StorageBackend,
)

logger = get_logger("openscire.provenance.tracker")


class ProvenanceTracker:
    """Singleton-per-project tracker that records, signs, and indexes provenance entries.

    Wraps a StorageBackend and ProvenanceGraph to provide a unified API
    for tracking research actions through the system.
    """

    _instances: dict[str, "ProvenanceTracker"] = {}

    def __init__(
        self,
        project_id: str,
        storage: StorageBackend | None = None,
        signing_key: str | None = None,
    ) -> None:
        self._project_id = project_id
        self._storage = storage or InMemoryBackend()
        self._graph = ProvenanceGraph()
        self._signing_key = signing_key
        self._last_action_id: str | None = None

    @classmethod
    def get_tracker(
        cls,
        project_id: str,
        storage_backend: str = "in_memory",
        db_path: str = "data/provenance.db",
        signing_key: str | None = None,
    ) -> "ProvenanceTracker":
        """Get or create a ProvenanceTracker singleton for a project.

        Args:
            project_id: Unique project identifier.
            storage_backend: Backend type (in_memory, sqlite, postgres).
            db_path: Path to SQLite database (if using sqlite backend).
            signing_key: Optional Ed25519 private key hex for signing.

        Returns:
            The singleton ProvenanceTracker for the given project.
        """
        if project_id not in cls._instances:
            storage = _create_storage(storage_backend, db_path)
            cls._instances[project_id] = cls(
                project_id=project_id,
                storage=storage,
                signing_key=signing_key,
            )
        return cls._instances[project_id]

    @classmethod
    def from_config(
        cls,
        project_id: str = "default",
        config: Config | None = None,
    ) -> "ProvenanceTracker":
        """Create a tracker from a Config object.

        Args:
            project_id: Unique project identifier.
            config: Config instance; uses default Config if None.

        Returns:
            Configured ProvenanceTracker.
        """
        cfg = config or Config()
        return cls.get_tracker(
            project_id=project_id,
            storage_backend=cfg.provenance.storage_backend,
            db_path=cfg.provenance.db_path,
            signing_key=_load_key(cfg.provenance.signing_key_path),
        )

    def track(
        self,
        action_type: str,
        agent_id: str = "",
        model_id: str = "",
        params: dict[str, object] | None = None,
        input_hash: str = "",
        output_hash: str = "",
        parent_ids: list[str] | None = None,
    ) -> ProvenanceEntry:
        """Record a provenance entry and optionally sign it.

        Automatically links to the previous action as parent if no
        parent_ids are specified.

        Args:
            action_type: Category label for the action.
            agent_id: Identifier of the agent performing the action.
            model_id: Identifier of the model used (if applicable).
            params: Snapshot of parameters or configuration used.
            input_hash: Hash of the input data.
            output_hash: Hash of the output data.
            parent_ids: Explicit parent action IDs; defaults to last action.

        Returns:
            The newly created ProvenanceEntry.
        """
        action_id = str(uuid.uuid4())
        if parent_ids is None and self._last_action_id is not None:
            parent_ids = [self._last_action_id]

        entry = ProvenanceEntry(
            action_id=action_id,
            action_type=action_type,
            parent_ids=parent_ids or [],
            agent_id=agent_id,
            model_id=model_id,
            parameters_snapshot=params or {},
            input_hash=input_hash,
            output_hash=output_hash,
            timestamp=datetime.now(timezone.utc),  # noqa: UP017
        )

        if self._signing_key is not None:
            entry = sign_entry(entry, self._signing_key)

        self._storage.save(entry)
        self._graph.add_entry(entry)
        self._last_action_id = action_id

        logger.info(
            "Provenance entry tracked",
            action_id=action_id,
            action_type=action_type,
            agent_id=agent_id,
            signed=entry.cryptographic_signature is not None,
        )
        return entry

    @property
    def storage(self) -> StorageBackend:
        return self._storage

    @property
    def graph(self) -> ProvenanceGraph:
        return self._graph

    @classmethod
    def reset(cls) -> None:
        """Clear all tracker instances (useful for testing)."""
        cls._instances.clear()


def _create_storage(
    backend: str,
    db_path: str = "data/provenance.db",
) -> StorageBackend:
    if backend == "in_memory":
        return InMemoryBackend()
    if backend == "sqlite":
        return SQLiteBackend(db_path)
    if backend == "postgres":
        return PostgresBackend()
    msg = f"Unknown storage backend: {backend}"
    raise ConfigError(msg, source="provenance.tracker", error_code=ErrorCode.CONFIG_INVALID)


def _load_key(path: str) -> str | None:
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        logger.warning("Could not load signing key", path=path)
        return None
