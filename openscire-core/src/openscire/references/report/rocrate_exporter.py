"""RO-Crate export for PedagogicalReport."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from openscire.references.report.models import PedagogicalReport, ReportSection


def to_ro_crate(report: PedagogicalReport) -> dict[str, Any]:
    """Render a PedagogicalReport as an RO-Crate 1.1 JSON-LD dict.

    Follows the same manual construction pattern as
    ``ProvenanceExporter.to_ro_crate()``.
    """
    graph: list[dict[str, Any]] = []

    # Metadata descriptor
    graph.append(
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {"@id": "./"},
            "conformsTo": {
                "@id": "https://w3id.org/ro/crate/1.1",
            },
        }
    )

    # Root data entity
    root: dict[str, Any] = {
        "@id": "./",
        "@type": "Dataset",
        "name": report.title,
        "description": report.description or report.title,
        "datePublished": report.generated_at.astimezone(timezone.utc).isoformat(),
    }
    if report.model_id:
        root["author"] = {"@id": f"#model-{report.model_id}"}

    # Section entities
    section_entities: list[dict[str, Any]] = []
    for s in report.sections:
        section_id = f"#section-{s.section.value}"
        section_entities.append(
            {
                "@id": section_id,
                "@type": "CreativeWork",
                "name": s.title or s.section.value.replace("_", " ").title(),
                "description": s.body[:500] if s.body else "",
                "text": s.body,
            }
        )
    if section_entities:
        root["hasPart"] = [
            {"@id": f"#section-{s.section.value}"} for s in report.sections
        ]

    graph.append(root)

    # Quantitative values as entities
    graph.append(
        {
            "@id": "#total-gaps",
            "@type": "QuantitativeValue",
            "name": "Total literature gaps identified",
            "value": report.total_gaps,
        }
    )
    graph.append(
        {
            "@id": "#unsupported-claims",
            "@type": "QuantitativeValue",
            "name": "Total unsupported claims",
            "value": report.total_unsupported_claims,
        }
    )
    graph.append(
        {
            "@id": "#cross-checks",
            "@type": "QuantitativeValue",
            "name": "Semantic cross-checks performed",
            "value": report.cross_checks_run,
        }
    )
    graph.append(
        {
            "@id": "#cross-checks-failed",
            "@type": "QuantitativeValue",
            "name": "Cross-checks flagged",
            "value": report.cross_checks_failed,
        }
    )

    graph.extend(section_entities)

    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": graph,
    }
