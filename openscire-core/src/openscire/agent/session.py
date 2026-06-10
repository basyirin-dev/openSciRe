# SPDX-License-Identifier: Apache-2.0

"""SessionManager — saves and restores research session state.

Serialises SessionState to JSON for fast operational restore, and records
a provenance entry for tamper-evident audit trails. The session hash links
all parent message IDs for full DAG traceability.
"""

import json
import os
from datetime import UTC, datetime
from typing import Any

from openscire.agent.models import SessionState


class SessionManager:
    """Persists and restores research session state.

    Args:
        storage_dir: Directory for session JSON files.
        provenance_tracker: Optional tracker for audit trail entries.
    """

    def __init__(
        self,
        storage_dir: str = ".sessions",
        provenance_tracker: Any | None = None,  # noqa: ANN401
    ) -> None:
        self._storage_dir = storage_dir
        self._provenance_tracker = provenance_tracker
        self._current_session: SessionState | None = None

    def save(
        self,
        state: SessionState,
        parent_message_ids: list[str] | None = None,
    ) -> str:
        """Save session state to JSON and optionally record in provenance.

        Args:
            state: The session state to persist.
            parent_message_ids: AgentBus message IDs for provenance linking.

        Returns:
            The file path of the saved session.
        """
        state.updated_at = datetime.now(UTC)
        self._current_session = state

        filepath = self._filepath(state.session_id)
        os.makedirs(self._storage_dir, exist_ok=True)

        with open(filepath, "w") as f:
            f.write(state.model_dump_json(indent=2))

        self._record_provenance(state, parent_message_ids or [])

        return filepath

    def restore(self, session_id: str) -> SessionState | None:
        """Restore session state from a JSON file.

        Args:
            session_id: The session ID to restore.

        Returns:
            The restored SessionState, or None if not found.
        """
        filepath = self._filepath(session_id)
        if not os.path.exists(filepath):
            return None

        with open(filepath) as f:
            data = json.load(f)

        state = SessionState.model_validate(data)
        self._current_session = state
        return state

    def delete(self, session_id: str) -> bool:
        """Delete a saved session file.

        Args:
            session_id: The session to delete.

        Returns:
            True if the file existed and was deleted, False otherwise.
        """
        filepath = self._filepath(session_id)
        if not os.path.exists(filepath):
            return False
        os.remove(filepath)
        return True

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all saved sessions with basic metadata.

        Returns:
            List of dicts with session_id, created_at, updated_at, state.
        """
        if not os.path.isdir(self._storage_dir):
            return []

        sessions: list[dict[str, Any]] = []
        for filename in sorted(os.listdir(self._storage_dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self._storage_dir, filename)
            try:
                with open(filepath) as f:
                    data = json.load(f)
                sessions.append(
                    {
                        "session_id": data.get("session_id", ""),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "state": data.get("supervisor_state", ""),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
        return sessions

    @property
    def current_session(self) -> SessionState | None:
        return self._current_session

    def _filepath(self, session_id: str) -> str:
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self._storage_dir, f"{safe_id}.json")

    def _record_provenance(
        self,
        state: SessionState,
        parent_message_ids: list[str],
    ) -> None:
        """Record the save operation in the provenance DAG."""
        if self._provenance_tracker is None:
            return

        from contextlib import suppress

        with suppress(Exception):
            self._provenance_tracker.track(
                action_type="session.save",
                agent_id="supervisor",
                params={
                    "session_id": state.session_id,
                    "supervisor_state": state.supervisor_state.value,
                    "task_count": len(state.plan.tasks) if state.plan else 0,
                    "conflict_count": len(state.conflicts),
                    "handoff_count": len(state.handoffs),
                },
                parent_ids=parent_message_ids or None,
            )
