"""Markdown export for PedagogicalReport."""

from __future__ import annotations

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


def to_markdown(report: PedagogicalReport) -> str:
    """Render a PedagogicalReport as Markdown."""

    section_map = {s.section: s for s in report.sections}

    lines: list[str] = []

    lines.append(f"# {report.title}")
    if report.description:
        lines.append("")
        lines.append(report.description)
    lines.append("")

    for section_type in _SECTION_ORDER:
        content = section_map.get(section_type)
        if content is None:
            continue

        lines.append(f"## {content.title or section_type.value.replace('_', ' ').title()}")
        lines.append("")
        for paragraph in content.body.split("\n"):
            lines.append(paragraph)
        lines.append("")

    lines.append("---")
    lines.append(f"*Report generated at: {report.generated_at.isoformat()}*")
    lines.append("")

    return "\n".join(lines)
