from openscire.references.gap.models import GapReport, GapSeverity, GapType, LiteratureGap


class TestGapType:
    def test_values(self) -> None:
        assert GapType.coverage == "coverage"
        assert GapType.methodological_monoculture == "methodological_monoculture"
        assert GapType.geographic == "geographic"
        assert GapType.temporal == "temporal"


class TestGapSeverity:
    def test_values(self) -> None:
        assert GapSeverity.high == "high"
        assert GapSeverity.medium == "medium"
        assert GapSeverity.low == "low"


class TestLiteratureGap:
    def test_defaults(self) -> None:
        gap = LiteratureGap(
            gap_type=GapType.coverage,
            severity=GapSeverity.high,
            topic="test",
            description="desc",
            recommendation="rec",
        )
        assert gap.affected_count == 0
        assert gap.details == {}

    def test_with_all_fields(self) -> None:
        gap = LiteratureGap(
            gap_type=GapType.temporal,
            severity=GapSeverity.medium,
            topic="ML",
            description="gap 2010-2015",
            recommendation="search more",
            affected_count=10,
            details={"gap_years": [2010, 2015]},
        )
        assert gap.gap_type == GapType.temporal
        assert gap.severity == GapSeverity.medium
        assert gap.topic == "ML"
        assert gap.details["gap_years"] == [2010, 2015]


class TestGapReport:
    def test_defaults(self) -> None:
        report = GapReport(topic="test")
        assert report.total_references == 0
        assert report.gaps == []
        assert report.config == {}
        assert report.generated_at is not None

    def test_with_gaps(self) -> None:
        gap = LiteratureGap(
            gap_type=GapType.coverage,
            severity=GapSeverity.high,
            topic="subtopic",
            description="desc",
            recommendation="rec",
        )
        report = GapReport(topic="main", total_references=42, gaps=[gap])
        assert report.total_references == 42
        assert len(report.gaps) == 1
        assert report.gaps[0].topic == "subtopic"
