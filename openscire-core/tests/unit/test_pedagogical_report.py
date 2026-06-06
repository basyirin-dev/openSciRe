"""Tests for PedagogicalReport — models, builder, and exporters."""

import json

import pytest

from openscire.references.report import (
    PedagogicalReport,
    PedagogicalReportBuilder,
    ReportSection,
    SectionContent,
    to_ipynb,
    to_markdown,
    to_ro_crate,
)
from openscire.references.report.builder import _confidence_label, _pct


# ---------------------------------------------------------------------------
# Helpers — minimal test double classes
# ---------------------------------------------------------------------------


class _FakeGap:
    def __init__(self, gap_type: str, severity: str, description: str,
                 recommendation: str = "", affected_count: int = 0) -> None:
        self.gap_type = gap_type
        self.severity = severity
        self.description = description
        self.recommendation = recommendation
        self.affected_count = affected_count


class _FakeGapReport:
    def __init__(self, gaps: list | None = None) -> None:
        self.gaps = gaps or []


class _FakeEnforcementReport:
    def __init__(self, total_sentences: int = 0, cited_sentences: int = 0,
                 unsupported_claims: list | None = None,
                 mode: str = "audit", cross_check_enabled: bool = False) -> None:
        self.total_sentences = total_sentences
        self.cited_sentences = cited_sentences
        self.unsupported_claims = unsupported_claims or []
        self.mode = mode
        self.cross_check_enabled = cross_check_enabled


class _FakeCrossCheckResult:
    def __init__(self, verdict: str, claim_text: str = "",
                 confidence: float = 0.0, explanation: str = "",
                 source_title: str = "") -> None:
        self.verdict = _FakeVerdict(verdict)
        self.claim_text = claim_text
        self.confidence = confidence
        self.explanation = explanation
        self.source_title = source_title


class _FakeVerdict:
    def __init__(self, value: str) -> None:
        self.value = value


class _FakeUnsupportedClaim:
    def __init__(self, reason: str) -> None:
        self.reason = reason


# ---------------------------------------------------------------------------
# Report models
# ---------------------------------------------------------------------------


class TestReportSection:
    def test_all_sections_present(self) -> None:
        values = [s.value for s in ReportSection]
        expected = [
            "executive_summary",
            "selection_rationale",
            "parameter_documentation",
            "alternative_interpretations",
            "self_identified_limitations",
            "uncertainty_indicators",
            "provenance",
        ]
        assert values == expected

    def test_members(self) -> None:
        assert len(ReportSection) == 7


class TestSectionContent:
    def test_defaults(self) -> None:
        c = SectionContent(section=ReportSection.EXECUTIVE_SUMMARY)
        assert c.body == ""
        assert c.data == {}

    def test_custom_values(self) -> None:
        c = SectionContent(
            section=ReportSection.EXECUTIVE_SUMMARY,
            title="Summary",
            body="Test body",
            data={"count": 5},
        )
        assert c.section == ReportSection.EXECUTIVE_SUMMARY
        assert c.body == "Test body"
        assert c.data == {"count": 5}


class TestPedagogicalReport:
    def test_defaults(self) -> None:
        r = PedagogicalReport()
        assert r.title == "Research Analysis Report"
        assert r.sections == []

    def test_custom_values(self) -> None:
        r = PedagogicalReport(
            title="My Report",
            description="Test",
            sections=[
                SectionContent(section=ReportSection.PROVENANCE, body="data")
            ],
            model_id="gpt-4",
            total_gaps=3,
        )
        assert r.title == "My Report"
        assert len(r.sections) == 1
        assert r.model_id == "gpt-4"
        assert r.total_gaps == 3


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class TestBuilder:
    def test_empty_build(self) -> None:
        builder = PedagogicalReportBuilder()
        report = builder.build()
        assert isinstance(report, PedagogicalReport)
        assert len(report.sections) == 7
        assert report.total_gaps == 0

    def test_build_with_gap_report(self) -> None:
        gaps = [
            _FakeGap("coverage", "high", "Missing sources in subtopic X", "Add more", 5),
            _FakeGap("geographic", "medium", "Western bias", "", 2),
        ]
        gr = _FakeGapReport(gaps)
        builder = PedagogicalReportBuilder()
        report = builder.add_gap_report(gr).build()
        assert report.total_gaps == 2
        rationale = next(s for s in report.sections if s.section == ReportSection.SELECTION_RATIONALE)
        assert "coverage" in rationale.body
        assert "geographic" in rationale.body

    def test_build_with_enforcement_report(self) -> None:
        er = _FakeEnforcementReport(total_sentences=10, cited_sentences=7,
                                    unsupported_claims=[_FakeUnsupportedClaim("no_citation")])
        builder = PedagogicalReportBuilder()
        report = builder.add_enforcement_report(er).build()
        summary = next(s for s in report.sections if s.section == ReportSection.EXECUTIVE_SUMMARY)
        assert "10" in summary.body
        assert "7" in summary.body

    def test_build_with_cross_check_results(self) -> None:
        results = [
            _FakeCrossCheckResult("supports", "Claim A", 0.95, "Matches", "Source A"),
            _FakeCrossCheckResult("contradicts", "Claim B", 0.8, "Opposite", "Source B"),
            _FakeCrossCheckResult("unverifiable", "Claim C", 0.0, "No text"),
        ]
        builder = PedagogicalReportBuilder()
        report = builder.add_cross_check_results(results).build()
        assert report.cross_checks_run == 3
        assert report.cross_checks_failed == 2  # contradicts + unverifiable

        alternatives = next(s for s in report.sections if s.section == ReportSection.ALTERNATIVE_INTERPRETATIONS)
        assert "Claim B" in alternatives.body

        limitations = next(s for s in report.sections if s.section == ReportSection.SELF_IDENTIFIED_LIMITATIONS)
        assert "Claim C" in limitations.body

        uncertainty = next(s for s in report.sections if s.section == ReportSection.UNCERTAINTY_INDICATORS)
        assert "Claim A" in uncertainty.body
        assert "high confidence" in uncertainty.body

    def test_build_with_metadata(self) -> None:
        builder = PedagogicalReportBuilder()
        report = (
            builder
            .set_model_id("claude-3.5")
            .set_retrieval_config({"top_k": 20, "threshold": 0.7})
            .set_generation_params({"temperature": 0.2})
            .build()
        )
        assert report.model_id == "claude-3.5"
        assert report.retrieval_config == {"top_k": 20, "threshold": 0.7}

        params = next(s for s in report.sections if s.section == ReportSection.PARAMETER_DOCUMENTATION)
        assert "claude-3.5" in params.body

    def test_chaining(self) -> None:
        builder = PedagogicalReportBuilder()
        assert builder.add_gap_report(_FakeGapReport()) is builder
        assert builder.set_model_id("test") is builder

    def test_no_gaps_shows_empty_message(self) -> None:
        builder = PedagogicalReportBuilder()
        report = builder.add_gap_report(_FakeGapReport([])).build()
        rationale = next(s for s in report.sections if s.section == ReportSection.SELECTION_RATIONALE)
        assert "No literature gaps" in rationale.body

    def test_no_cross_checks_shows_no_alternatives_message(self) -> None:
        builder = PedagogicalReportBuilder()
        report = builder.build()
        alt = next(s for s in report.sections if s.section == ReportSection.ALTERNATIVE_INTERPRETATIONS)
        assert "No alternative interpretations" in alt.body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_pct(self) -> None:
        assert _pct(3, 10) == 30.0
        assert _pct(0, 10) == 0.0
        assert _pct(0, 0) == 0.0

    def test_confidence_label(self) -> None:
        assert _confidence_label(0.95) == "high confidence"
        assert _confidence_label(0.65) == "moderate confidence"
        assert _confidence_label(0.35) == "low confidence"
        assert _confidence_label(0.05) == "very low confidence"
        assert _confidence_label(0.0) == "very low confidence"


# ---------------------------------------------------------------------------
# Markdown exporter
# ---------------------------------------------------------------------------


class TestMarkdownExport:
    def test_renders_all_sections(self) -> None:
        report = PedagogicalReportBuilder().build()
        md = to_markdown(report)
        assert md.startswith("# ")
        assert "## Executive Summary" in md
        assert "## Selection Rationale" in md
        assert "## Parameter Documentation" in md
        assert "## Alternative Interpretations" in md
        assert "## Self-Identified Limitations" in md
        assert "## Uncertainty Indicators" in md
        assert "## Provenance" in md

    def test_includes_title(self) -> None:
        report = PedagogicalReport(title="Test Report")
        md = to_markdown(report)
        assert "# Test Report" in md

    def test_includes_description(self) -> None:
        report = PedagogicalReport(description="A description")
        md = to_markdown(report)
        assert "A description" in md

    def test_includes_timestamp(self) -> None:
        report = PedagogicalReportBuilder().build()
        md = to_markdown(report)
        assert "Report generated at:" in md


# ---------------------------------------------------------------------------
# Jupyter exporter
# ---------------------------------------------------------------------------


class TestJupyterExport:
    def test_valid_json(self) -> None:
        report = PedagogicalReportBuilder().build()
        raw = to_ipynb(report)
        data = json.loads(raw)
        assert data["nbformat"] == 4
        assert "cells" in data

    def test_cell_count(self) -> None:
        report = PedagogicalReportBuilder().build()
        data = json.loads(to_ipynb(report))
        # 1 title + 2 metadata/counts + 7*2 (markdown+code) + 1 footer = 17
        assert len(data["cells"]) >= 10

    def test_cell_types(self) -> None:
        report = PedagogicalReportBuilder().build()
        data = json.loads(to_ipynb(report))
        md_count = sum(1 for c in data["cells"] if c["cell_type"] == "markdown")
        code_count = sum(1 for c in data["cells"] if c["cell_type"] == "code")
        assert md_count >= 1
        assert code_count >= 1

    def test_contains_title(self) -> None:
        report = PedagogicalReport(title="My Report")
        data = json.loads(to_ipynb(report))
        first_cell = data["cells"][0]
        assert any("My Report" in line for line in first_cell["source"])

    def test_contains_counts(self) -> None:
        report = PedagogicalReportBuilder().build()
        data = json.loads(to_ipynb(report))
        sources = "\n".join(
            "\n".join(c["source"]) for c in data["cells"] if c["cell_type"] == "code"
        )
        assert "total_gaps" in sources
        assert "cross_checks_run" in sources


# ---------------------------------------------------------------------------
# RO-Crate exporter
# ---------------------------------------------------------------------------


class TestROCrateExport:
    def test_valid_jsonld(self) -> None:
        report = PedagogicalReportBuilder().build()
        crate = to_ro_crate(report)
        assert crate["@context"] == "https://w3id.org/ro/crate/1.1/context"
        assert "@graph" in crate

    def test_root_entity(self) -> None:
        report = PedagogicalReport(title="Test")
        crate = to_ro_crate(report)
        root = next(e for e in crate["@graph"] if e.get("@id") == "./")
        assert root["name"] == "Test"
        assert root["@type"] == "Dataset"

    def test_metadata_descriptor(self) -> None:
        report = PedagogicalReportBuilder().build()
        crate = to_ro_crate(report)
        md = next(e for e in crate["@graph"] if e.get("@id") == "ro-crate-metadata.json")
        assert md["@type"] == "CreativeWork"

    def test_quantitative_values(self) -> None:
        report = PedagogicalReport(
            total_gaps=5, total_unsupported_claims=3,
            cross_checks_run=10, cross_checks_failed=2,
        )
        crate = to_ro_crate(report)
        qvs = [e for e in crate["@graph"] if e.get("@type") == "QuantitativeValue"]
        ids = [qv["@id"] for qv in qvs]
        assert "#total-gaps" in ids
        assert "#cross-checks-failed" in ids
        gap_qv = next(qv for qv in qvs if qv["@id"] == "#total-gaps")
        assert gap_qv["value"] == 5

    def test_section_entities(self) -> None:
        report = PedagogicalReportBuilder().build()
        crate = to_ro_crate(report)
        sections = [e for e in crate["@graph"] if e.get("@type") == "CreativeWork"
                    and e["@id"].startswith("#section-")]
        assert len(sections) == 7  # one per ReportSection


# ---------------------------------------------------------------------------
# No artifact modes — design constraint
# ---------------------------------------------------------------------------


class TestNoArtifactModes:
    def test_no_slide_methods(self) -> None:
        builder = PedagogicalReportBuilder()
        assert not hasattr(builder, "to_slides")
        assert not hasattr(builder, "to_pptx")
        assert not hasattr(builder, "to_html_slides")

    def test_no_audio_methods(self) -> None:
        builder = PedagogicalReportBuilder()
        assert not hasattr(builder, "to_audio")
        assert not hasattr(builder, "to_podcast")
        assert not hasattr(builder, "to_speech")

    def test_no_video_methods(self) -> None:
        builder = PedagogicalReportBuilder()
        assert not hasattr(builder, "to_video")
        assert not hasattr(builder, "to_mp4")
        assert not hasattr(builder, "to_webm")

    def test_only_three_export_functions(self) -> None:
        from openscire.references.report import __all__ as report_exports
        export_funcs = [e for e in report_exports if e.startswith("to_")]
        assert set(export_funcs) == {"to_markdown", "to_ipynb", "to_ro_crate"}
