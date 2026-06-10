"""Jupyter notebook export for PedagogicalReport."""

from __future__ import annotations

import json

from openscire.references.report.models import PedagogicalReport, ReportSection

_SECTION_ORDER: list[ReportSection] = [
    ReportSection.EXECUTIVE_SUMMARY,
    ReportSection.SELECTION_RATIONALE,
    ReportSection.PARAMETER_DOCUMENTATION,
    ReportSection.ALTERNATIVE_INTERPRETATIONS,
    ReportSection.SELF_IDENTIFIED_LIMITATIONS,
    ReportSection.UNCERTAINTY_INDICATORS,
    ReportSection.PROVENANCE,
]


def to_ipynb(report: PedagogicalReport) -> str:
    """Render a PedagogicalReport as a Jupyter notebook JSON string.

    Uses nbformat v4 schema (no ``nbformat`` library dependency required
    for the JSON structure — the schema is stable and well-documented).
    """
    section_map = {s.section: s for s in report.sections}

    cells: list[dict] = []

    # Title + description markdown cell
    title_parts = [f"# {report.title}"]
    if report.description:
        title_parts.append("")
        title_parts.append(report.description)
    cells.append(_md_cell("\n".join(title_parts)))

    # Metadata code cell
    metadata_lines = [
        '"""',
        "Analysis metadata",
        "=================",
        "",
    ]
    if report.model_id:
        metadata_lines.append(f"Model: {report.model_id}")
    if report.retrieval_config:
        metadata_lines.append(f"Retrieval config: {json.dumps(report.retrieval_config, indent=2)}")
    if report.generation_params:
        metadata_lines.append(
            f"Generation params: {json.dumps(report.generation_params, indent=2)}"
        )
    metadata_lines.append('"""')
    cells.append(_code_cell("\n".join(metadata_lines)))

    # Counts code cell
    counts_lines = [
        "# Summary counts",
        f"total_gaps = {report.total_gaps}",
        f"total_unsupported_claims = {report.total_unsupported_claims}",
        f"cross_checks_run = {report.cross_checks_run}",
        f"cross_checks_failed = {report.cross_checks_failed}",
    ]
    cells.append(_code_cell("\n".join(counts_lines)))

    # Section cells
    for section_type in _SECTION_ORDER:
        content = section_map.get(section_type)
        if content is None:
            continue

        cells.append(
            _md_cell(
                f"## {content.title or section_type.value.replace('_', ' ').title()}\n\n"
                f"{content.body}"
            )
        )

        if content.data:
            data_json = json.dumps(content.data, indent=2, default=str)
            cells.append(_code_cell(f"# {content.title} — structured data\ndata = {data_json}"))

    # Footer markdown
    cells.append(_md_cell(f"---\n*Report generated at: {report.generated_at.isoformat()}*"))

    notebook: dict = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3",
            },
        },
        "cells": cells,
    }

    return json.dumps(notebook, indent=1, ensure_ascii=False)


def _md_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.split("\n") if isinstance(source, str) else source,
    }


def _code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.split("\n") if isinstance(source, str) else source,
    }
