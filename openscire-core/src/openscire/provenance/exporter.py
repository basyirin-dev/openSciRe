# SPDX-License-Identifier: Apache-2.0

"""Export provenance entries to JSON, RO-Crate, and W3C PROV-O formats."""

import json

from openscire.models import ProvenanceEntry


class ProvenanceExporter:
    """Static exporter for provenance entries in multiple standard formats."""

    @staticmethod
    def to_json(
        entries: list[ProvenanceEntry],
        root_hash: str = "",
    ) -> str:
        """Export provenance entries as a JSON string.

        Args:
            entries: List of ProvenanceEntry objects.
            root_hash: Optional Merkle root hash to include.

        Returns:
            Pretty-printed JSON string.
        """
        payload: dict[str, object] = {
            "provenance": [e.model_dump(mode="json") for e in entries],
        }
        if root_hash:
            payload["root_hash"] = root_hash
        return json.dumps(payload, indent=2, default=str)

    @staticmethod
    def to_ro_crate(
        entries: list[ProvenanceEntry],
    ) -> dict[str, object]:
        """Export provenance entries as an RO-Crate JSON-LD structure.

        Args:
            entries: List of ProvenanceEntry objects.

        Returns:
            Dict conforming to the RO-Crate 1.1 JSON-LD context.
        """
        graph: list[dict[str, object]] = []
        for e in entries:
            entity: dict[str, object] = {
                "@id": e.action_id,
                "@type": "Entity",
                "name": e.action_type or "Provenance Entry",
                "description": f"Action {e.action_id} by {e.agent_id}",
                "agent": e.agent_id,
            }
            if e.parent_ids:
                entity["wasDerivedFrom"] = [{"@id": pid} for pid in e.parent_ids]
            graph.append(entity)

        return {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": graph,
        }

    @staticmethod
    def to_w3c_prov(
        entries: list[ProvenanceEntry],
    ) -> dict[str, object]:
        """Export provenance entries as W3C PROV-O JSON.

        Args:
            entries: List of ProvenanceEntry objects.

        Returns:
            Dict with PROV-O entity and activity structures.
        """
        entities: dict[str, dict[str, object]] = {}
        activities: dict[str, dict[str, object]] = {}

        for e in entries:
            eid = e.action_id
            entities[eid] = {
                "prov:label": e.action_type or "Entry",
                "prov:type": "prov:Entity",
            }
            if e.agent_id:
                entities[eid]["prov:attributedTo"] = e.agent_id
            if e.parent_ids:
                entities[eid]["prov:wasDerivedFrom"] = [pid for pid in e.parent_ids]

            aid = f"activity:{eid}"
            activities[aid] = {
                "prov:label": f"Action: {e.action_type}",
                "prov:type": "prov:Activity",
                "prov:startedAtTime": e.timestamp.isoformat(),
                "prov:wasAssociatedWith": e.agent_id,
            }

        return {
            "prefix": {
                "prov": "http://www.w3.org/ns/prov#",
            },
            "entity": entities,
            "activity": activities,
        }
