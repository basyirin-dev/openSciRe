"""PedagogicalReportBuilder — aggregates sub-reports into a structured report."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from openscire.references.report.models import (
    PedagogicalReport,
    ReportSection,
    SectionContent,
)


class PedagogicalReportBuilder:
    """Fluent builder that ingests analysis outputs and produces a
    PedagogicalReport with transparency-oriented sections."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        provenance_tracker: Any = None,
    ) -> None:
        self._config = config or {}
        self._provenance_tracker = provenance_tracker

        self._gap_report: Any = None
        self._enforcement_report: Any = None
        self._cross_check_results: list[Any] = []
        self._context_package: Any = None
        self._uncertainty_report: Any = None

        self._model_id: str = ""
        self._retrieval_config: dict[str, Any] = {}
        self._generation_params: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_gap_report(self, report: Any) -> PedagogicalReportBuilder:
        self._gap_report = report
        return self

    def add_enforcement_report(self, report: Any) -> PedagogicalReportBuilder:
        self._enforcement_report = report
        return self

    def add_cross_check_results(
        self, results: list[Any]
    ) -> PedagogicalReportBuilder:
        self._cross_check_results = list(results)
        return self

    def add_context_package(self, pkg: Any) -> PedagogicalReportBuilder:
        self._context_package = pkg
        return self

    def add_uncertainty_report(self, report: Any) -> PedagogicalReportBuilder:
        self._uncertainty_report = report
        return self

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def set_model_id(self, model_id: str) -> PedagogicalReportBuilder:
        self._model_id = model_id
        return self

    def set_retrieval_config(
        self, config: dict[str, Any]
    ) -> PedagogicalReportBuilder:
        self._retrieval_config = dict(config)
        return self

    def set_generation_params(
        self, params: dict[str, Any]
    ) -> PedagogicalReportBuilder:
        self._generation_params = dict(params)
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> PedagogicalReport:
        sections: list[SectionContent] = []

        self._build_executive_summary(sections)
        self._build_selection_rationale(sections)
        self._build_parameter_documentation(sections)
        self._build_alternative_interpretations(sections)
        self._build_self_identified_limitations(sections)
        self._build_uncertainty_indicators(sections)
        self._build_provenance(sections)

        counts = self._compute_counts()

        return PedagogicalReport(
            title=self._config.get("title", "Research Analysis Report"),
            description=self._config.get("description", ""),
            generated_at=datetime.now(timezone.utc),
            sections=sections,
            model_id=self._model_id,
            retrieval_config=self._retrieval_config,
            generation_params=self._generation_params,
            **counts,
        )

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_executive_summary(
        self, sections: list[SectionContent]
    ) -> None:
        lines: list[str] = []
        er = self._enforcement_report
        gr = self._gap_report

        total_claims = getattr(er, "total_sentences", 0) if er else 0
        cited = getattr(er, "cited_sentences", 0) if er else 0
        unsupported = (
            len(getattr(er, "unsupported_claims", [])) if er else 0
        )
        gaps = len(getattr(gr, "gaps", [])) if gr else 0
        xc = len(self._cross_check_results)
        xc_failed = sum(
            1
            for r in self._cross_check_results
            if getattr(r, "verdict", None) is not None
            and r.verdict.value
            in ("contradicts", "insufficient_evidence", "unverifiable")
        )

        lines.append(
            f"This report summarizes the analysis of {total_claims} "
            f"claims across the research topic."
        )
        lines.append("")
        lines.append(
            f"**Cited claims**: {cited}/{total_claims} "
            f"({_pct(cited, total_claims)}%)"
        )
        lines.append(
            f"**Unsupported claims**: {unsupported}"
        )
        lines.append(f"**Literature gaps identified**: {gaps}")
        lines.append(
            f"**Semantic cross-checks performed**: {xc} "
            f"({xc_failed} flagged)"
        )
        if self._model_id:
            lines.append(
                f"**Analysis model**: {self._model_id}"
            )

        sections.append(
            SectionContent(
                section=ReportSection.EXECUTIVE_SUMMARY,
                title="Executive Summary",
                body="\n".join(lines),
                data={
                    "total_claims": total_claims,
                    "cited_claims": cited,
                    "unsupported_claims": unsupported,
                    "total_gaps": gaps,
                    "cross_checks_performed": xc,
                    "cross_checks_flagged": xc_failed,
                },
            )
        )

    def _build_selection_rationale(
        self, sections: list[SectionContent]
    ) -> None:
        gr = self._gap_report
        gaps = getattr(gr, "gaps", []) if gr else []

        if not gaps:
            sections.append(
                SectionContent(
                    section=ReportSection.SELECTION_RATIONALE,
                    title="Selection Rationale",
                    body="No literature gaps were detected in the source selection.",
                    data={},
                )
            )
            return

        lines = [
            "Sources were evaluated against the following gap criteria:"
        ]
        for g in gaps:
            gap_type = getattr(g, "gap_type", "unknown")
            severity = getattr(g, "severity", "unknown")
            desc = getattr(g, "description", "")
            rec = getattr(g, "recommendation", "")
            affected = getattr(g, "affected_count", 0)
            lines.append("")
            lines.append(f"- **{gap_type}** ({severity}, {affected} sources): {desc}")
            if rec:
                lines.append(f"  - Recommendation: {rec}")

        sections.append(
            SectionContent(
                section=ReportSection.SELECTION_RATIONALE,
                title="Selection Rationale",
                body="\n".join(lines),
                data={
                    "total_gaps": len(gaps),
                    "gaps": [
                        {
                            "type": str(getattr(g, "gap_type", "")),
                            "severity": str(getattr(g, "severity", "")),
                            "description": getattr(g, "description", ""),
                        }
                        for g in gaps
                    ],
                },
            )
        )

    def _build_parameter_documentation(
        self, sections: list[SectionContent]
    ) -> None:
        lines: list[str] = []

        if self._model_id:
            lines.append(f"- **Model**: {self._model_id}")

        if self._retrieval_config:
            lines.append("- **Retrieval configuration**:")
            for key, val in self._retrieval_config.items():
                lines.append(f"  - `{key}`: {val}")

        if self._generation_params:
            lines.append("- **Generation parameters**:")
            for key, val in self._generation_params.items():
                lines.append(f"  - `{key}`: {val}")

        er = self._enforcement_report
        if er is not None:
            mode = getattr(er, "mode", "unknown")
            lines.append(
                f"- **Enforcement mode**: {mode}"
            )
            xc_enabled = getattr(er, "cross_check_enabled", False)
            lines.append(
                f"- **Semantic cross-check**: {'enabled' if xc_enabled else 'disabled'}"
            )

        if not lines:
            lines.append("No parameter documentation was provided.")

        sections.append(
            SectionContent(
                section=ReportSection.PARAMETER_DOCUMENTATION,
                title="Parameter Documentation",
                body="\n".join(lines),
                data={
                    "model_id": self._model_id,
                    "retrieval_config": self._retrieval_config,
                    "generation_params": self._generation_params,
                },
            )
        )

    def _build_alternative_interpretations(
        self, sections: list[SectionContent]
    ) -> None:
        lines: list[str] = []
        data_items: list[dict[str, Any]] = []

        for r in self._cross_check_results:
            verdict = getattr(r, "verdict", None)
            if verdict is not None and verdict.value in (
                "contradicts",
                "ambiguous",
            ):
                claim = getattr(r, "claim_text", "")
                explanation = getattr(r, "explanation", "")
                confidence = getattr(r, "confidence", 0.0)
                source_title = getattr(r, "source_title", "")
                lines.append("")
                lines.append(
                    f'- Claim: "{claim}"'
                )
                if explanation:
                    lines.append(f"  - {explanation}")
                lines.append(f"  - Confidence: {confidence:.2f}")
                if source_title:
                    lines.append(f"  - Source: {source_title}")
                data_items.append(
                    {
                        "claim": claim,
                        "verdict": verdict.value,
                        "explanation": explanation,
                        "confidence": confidence,
                    }
                )

        if not lines:
            lines.append(
                "No alternative interpretations were identified. "
                "All cross-checked claims were consistent with their sources."
            )

        sections.append(
            SectionContent(
                section=ReportSection.ALTERNATIVE_INTERPRETATIONS,
                title="Alternative Interpretations",
                body="\n".join(lines),
                data={"alternatives": data_items},
            )
        )

    def _build_self_identified_limitations(
        self, sections: list[SectionContent]
    ) -> None:
        lines: list[str] = []
        data_items: list[dict[str, Any]] = []

        for r in self._cross_check_results:
            verdict = getattr(r, "verdict", None)
            if verdict is not None and verdict.value == "unverifiable":
                claim = getattr(r, "claim_text", "")
                explanation = getattr(r, "explanation", "")
                lines.append("")
                lines.append(f'- Claim: "{claim}"')
                if explanation:
                    lines.append(f"  - {explanation}")
                data_items.append(
                    {
                        "claim": claim,
                        "reason": explanation,
                    }
                )

        er = self._enforcement_report
        if er is not None:
            unsupported = getattr(er, "unsupported_claims", [])
            no_citation = [
                u
                for u in unsupported
                if getattr(u, "reason", "") == "no_citation"
            ]
            if no_citation:
                lines.append("")
                lines.append(
                    f"- {len(no_citation)} claim(s) were made without "
                    f"supporting citations."
                )
                data_items.append(
                    {
                        "reason": "no_citation",
                        "count": len(no_citation),
                    }
                )

        if not lines:
            lines.append(
                "No self-identified limitations were recorded for this analysis."
            )

        sections.append(
            SectionContent(
                section=ReportSection.SELF_IDENTIFIED_LIMITATIONS,
                title="Self-Identified Limitations",
                body="\n".join(lines),
                data={"limitations": data_items},
            )
        )

    def _build_uncertainty_indicators(
        self, sections: list[SectionContent]
    ) -> None:
        lines: list[str] = []
        data_items: list[dict[str, Any]] = []

        for r in self._cross_check_results:
            verdict = getattr(r, "verdict", None)
            confidence = getattr(r, "confidence", 0.0)
            claim = getattr(r, "claim_text", "")
            source_title = getattr(r, "source_title", "")

            label = _confidence_label(confidence)
            lines.append("")
            lines.append(
                f'- Claim: "{claim}" → {label} ({confidence:.2f})'
            )
            if verdict is not None:
                lines.append(f"  - Verdict: {verdict.value}")
            if source_title:
                lines.append(f"  - Source: {source_title}")
            data_items.append(
                {
                    "claim": claim,
                    "verdict": verdict.value if verdict else "unknown",
                    "confidence": confidence,
                    "label": label,
                }
            )

        if not lines:
            lines.append(
                "No uncertainty indicators were recorded "
                "(no cross-checks performed)."
            )

        sections.append(
            SectionContent(
                section=ReportSection.UNCERTAINTY_INDICATORS,
                title="Uncertainty Indicators",
                body="\n".join(lines),
                data={"indicators": data_items},
            )
        )

    def _build_provenance(self, sections: list[SectionContent]) -> None:
        lines: list[str] = [
            f"- **Generated at**: {datetime.now(timezone.utc).isoformat()}"
        ]
        if self._model_id:
            lines.append(f"- **Analysis model**: {self._model_id}")
        lines.append(
            "- **Components**: gap analysis, citation enforcement, "
            "semantic cross-check"
        )

        if self._provenance_tracker is not None:
            lines.append("- **Provenance tracking**: enabled")
            try:
                self._provenance_tracker.track(
                    action_type="build_pedagogical_report",
                    agent_id="PedagogicalReportBuilder",
                    model_id=self._model_id,
                )
            except Exception:
                pass

        sections.append(
            SectionContent(
                section=ReportSection.PROVENANCE,
                title="Provenance",
                body="\n".join(lines),
                data={"generated_at": datetime.now(timezone.utc).isoformat()},
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_counts(self) -> dict[str, Any]:
        er = self._enforcement_report
        gr = self._gap_report

        total_gaps = len(getattr(gr, "gaps", [])) if gr else 0
        total_unsupported = (
            len(getattr(er, "unsupported_claims", [])) if er else 0
        )
        xc = len(self._cross_check_results)
        xc_failed = sum(
            1
            for r in self._cross_check_results
            if getattr(r, "verdict", None) is not None
            and r.verdict.value
            in ("contradicts", "insufficient_evidence", "unverifiable")
        )

        return {
            "total_gaps": total_gaps,
            "total_unsupported_claims": total_unsupported,
            "cross_checks_run": xc,
            "cross_checks_failed": xc_failed,
        }


def _pct(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, 1)


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "high confidence"
    if confidence >= 0.5:
        return "moderate confidence"
    if confidence >= 0.2:
        return "low confidence"
    return "very low confidence"
