# SPDX-License-Identifier: Apache-2.0

"""Anti-HARKing enforcer — validates temporal ordering of hypotheses and evidence."""

from openscire.logging import get_logger
from openscire.models import ProvenanceEntry

from .tracker import ProvenanceTracker

logger = get_logger("openscire.provenance.enforcer")


class ResearchChronologyEnforcer:
    """Enforces temporal ordering to prevent HARKing (hypothesizing after results are known)."""

    def __init__(self, tracker: ProvenanceTracker) -> None:
        self._tracker = tracker
        self._graph = tracker.graph

    def stamp_hypothesis(self, hypothesis_id: str) -> ProvenanceEntry:
        """Register a hypothesis in the provenance graph with a timestamp.

        Args:
            hypothesis_id: Unique identifier for the hypothesis.

        Returns:
            The provenance entry created for the registration.
        """
        return self._tracker.track(
            action_type="hypothesis_registered",
            agent_id="chronology_enforcer",
            params={"hypothesis_id": hypothesis_id},
            input_hash=hypothesis_id,
        )

    def check_evidence(
        self,
        hypothesis_id: str,
        evidence_entry: ProvenanceEntry,
    ) -> bool:
        """Verify that evidence was collected after the hypothesis was registered.

        Args:
            hypothesis_id: The hypothesis to check against.
            evidence_entry: The evidence entry to validate.

        Returns:
            True if evidence timestamp is after hypothesis registration.
        """
        hypothesis_entries = self._graph.query(
            action_type="hypothesis_registered",
        )
        hypothesis_entry: ProvenanceEntry | None = None
        for he in hypothesis_entries:
            params = he.parameters_snapshot
            if isinstance(params, dict) and params.get("hypothesis_id") == hypothesis_id:
                hypothesis_entry = he
                break

        if hypothesis_entry is None:
            logger.warning(
                "No hypothesis registration found",
                hypothesis_id=hypothesis_id,
            )
            return False

        if evidence_entry.timestamp < hypothesis_entry.timestamp:
            logger.warning(
                "Temporal ordering violation detected (HARKing)",
                hypothesis_id=hypothesis_id,
                evidence_id=evidence_entry.action_id,
                hypothesis_timestamp=hypothesis_entry.timestamp.isoformat(),
                evidence_timestamp=evidence_entry.timestamp.isoformat(),
            )
            return False

        return True

    def detect_temporal_anomalies(
        self,
        hypothesis_id: str,
    ) -> list[dict[str, object]]:
        """Scan the provenance graph for temporal ordering violations.

        Args:
            hypothesis_id: The hypothesis to audit.

        Returns:
            List of anomaly dicts with type, severity, and detail.
        """
        hypothesis_entries = self._graph.query(
            action_type="hypothesis_registered",
        )
        hypothesis_entry: ProvenanceEntry | None = None
        for he in hypothesis_entries:
            params = he.parameters_snapshot
            if isinstance(params, dict) and params.get("hypothesis_id") == hypothesis_id:
                hypothesis_entry = he
                break

        if hypothesis_entry is None:
            return [
                {
                    "type": "missing_hypothesis",
                    "hypothesis_id": hypothesis_id,
                    "detail": "No hypothesis_registered entry found in provenance graph",
                }
            ]

        anomalies: list[dict[str, object]] = []
        for entry in self._traverse_connected(hypothesis_entry.action_id):
            if entry.timestamp < hypothesis_entry.timestamp:
                anomalies.append(
                    {
                        "type": "temporal_ordering_violation",
                        "hypothesis_id": hypothesis_id,
                        "hypothesis_timestamp": hypothesis_entry.timestamp.isoformat(),
                        "evidence_id": entry.action_id,
                        "evidence_type": entry.action_type,
                        "evidence_timestamp": entry.timestamp.isoformat(),
                        "severity": "high",
                    }
                )

        return anomalies

    def _traverse_connected(self, start_id: str) -> list[ProvenanceEntry]:
        seen: set[str] = set()
        result: list[ProvenanceEntry] = []
        for direction in ("forward", "backward"):
            for entry in self._graph.traverse(start_id, direction=direction):
                if entry.action_id not in seen:
                    seen.add(entry.action_id)
                    result.append(entry)
        return result
