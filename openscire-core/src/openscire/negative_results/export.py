# SPDX-License-Identifier: Apache-2.0

"""Export negative results to JSON, CSV and RO-Crate."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from openscire.negative_results.models import NegativeResult

_RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"


class NegativeResultExporter:
    """Static methods for exporting batches of negative results."""

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------

    @staticmethod
    def to_json(results: list[NegativeResult], indent: int = 2) -> str:
        """Serialize results to a JSON string.

        Each result is ``model_dump(mode="json")``-ed so datetimes
        become ISO strings and enums become their values.
        """
        raw = [r.model_dump(mode="json") for r in results]
        return json.dumps(raw, indent=indent, default=str)

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    @staticmethod
    def to_csv(results: list[NegativeResult]) -> str:
        """Serialize results to a CSV string.

        List fields (``suggestions``, ``source_references``,
        ``domain_tags``) are serialized as JSON strings in their
        respective columns.
        """
        buf = io.StringIO()
        fieldnames = [
            "result_id",
            "hypothesis",
            "method_used",
            "data_summary",
            "outcome",
            "confidence",
            "reason_for_failure",
            "suggestions",
            "source_references",
            "domain_tags",
            "created_at",
            "created_by",
            "ttl_days",
            "expires_at",
            "provenance_entry_id",
        ]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {
                "result_id": r.result_id,
                "hypothesis": r.hypothesis,
                "method_used": r.method_used,
                "data_summary": r.data_summary,
                "outcome": r.outcome.value,
                "confidence": r.confidence,
                "reason_for_failure": r.reason_for_failure,
                "suggestions": json.dumps(r.suggestions),
                "source_references": json.dumps(r.source_references),
                "domain_tags": json.dumps(r.domain_tags),
                "created_at": r.created_at.isoformat(),
                "created_by": r.created_by,
                "ttl_days": r.ttl_days,
                "expires_at": r.expires_at.isoformat() if r.expires_at else "",
                "provenance_entry_id": r.provenance_entry_id or "",
            }
            writer.writerow(row)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # RO-Crate export
    # ------------------------------------------------------------------

    @staticmethod
    def to_ro_crate(
        results: list[NegativeResult],
        dataset_name: str = "Negative Results Export",
    ) -> dict[str, Any]:
        """Build an RO-Crate 1.1 JSON-LD dict from a list of results.

        The crate contains:
        * A root ``Dataset`` entity describing the export.
        * One ``Dataset`` entity per negative result, linked via
          ``hasPart`` → ``isPartOf``.
        """
        now = datetime.now(UTC).isoformat()
        root_id = "./"

        entities: list[dict[str, Any]] = [
            {
                "@id": root_id,
                "@type": "Dataset",
                "name": dataset_name,
                "datePublished": now,
                "description": (
                    "Export of negative results from the openSciRe Negative Result Registry."
                ),
                "hasPart": [],
            },
        ]

        for r in results:
            result_id = f"#negresult-{r.result_id}"
            entity: dict[str, Any] = {
                "@id": result_id,
                "@type": "Dataset",
                "name": f"Negative result: {r.hypothesis[:120]}",
                "description": r.reason_for_failure or r.data_summary,
                "dateCreated": r.created_at.isoformat(),
                "isPartOf": {"@id": root_id},
                "outcome": r.outcome.value,
                "methodUsed": r.method_used,
                "confidence": r.confidence,
                "suggestions": r.suggestions,
            }
            if r.domain_tags:
                entity["keywords"]: list[str] = r.domain_tags
            if r.source_references:
                entity["citation"]: list[str] = r.source_references
            entities.append(entity)
            entities[0]["hasPart"].append({"@id": result_id})

        return {
            "@context": _RO_CRATE_CONTEXT,
            "@graph": entities,
        }
