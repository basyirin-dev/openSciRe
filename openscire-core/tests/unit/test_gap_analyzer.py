import pytest
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource

try:
    from openscire.references.gap.analyzer import GapAnalyzer
except ImportError:
    pytestmark = pytest.mark.skip("GapAnalyzer not available")


def _make_ref(
    source: ReferenceSource = ReferenceSource.pubmed,
    year: int | None = 2020,
    language: str = "en",
    keywords: list[str] | None = None,
    title: str = "Test",
    abstract: str = "",
) -> ReferenceItem:
    return ReferenceItem(
        id=f"{source.value}-{year}",
        source=source,
        title=title,
        abstract=abstract,
        year=year,
        original_language=language,
        keywords=keywords or [],
        authors=[ReferenceAuthor(first="A", last="B")],
    )


class TestGapAnalyzer:
    def test_full_analysis_no_gaps(self) -> None:
        analyzer = GapAnalyzer(
            {
                "gap_min_sources": 2,
                "gap_min_papers": 1,
                "gap_min_method_categories": 2,
                "gap_min_gap_years": 5,
                "gap_recency_years": 10,
            }
        )
        items = [
            _make_ref(ReferenceSource.pubmed, 2025, language="en", abstract="In vitro cell study"),
            _make_ref(
                ReferenceSource.semantic_scholar,
                2026,
                language="zh",
                abstract="Clinical trial results",
            ),
        ]
        report = analyzer.analyze("cancer", items)
        assert report.topic == "cancer"
        assert report.total_references == 2
        assert len(report.gaps) == 0

    def test_full_analysis_with_gaps(self) -> None:
        analyzer = GapAnalyzer(
            {
                "gap_min_sources": 3,
                "gap_min_papers": 1,
                "gap_min_method_categories": 3,
                "gap_min_gap_years": 2,
                "gap_recency_years": 99,
            }
        )
        items = [
            _make_ref(ReferenceSource.pubmed, 2020, language="en", abstract="In vitro cell study"),
            _make_ref(ReferenceSource.pubmed, 2010, language="zh", abstract="In vitro cell study"),
        ]
        report = analyzer.analyze("cancer", items)
        assert report.topic == "cancer"
        assert len(report.gaps) >= 1

    def test_individual_detectors(self) -> None:
        analyzer = GapAnalyzer()
        items = [_make_ref()]
        cov = analyzer.detect_coverage("t", {"sub": items})
        meth = analyzer.detect_methodology("t", items)
        geo = analyzer.detect_geography("t", items)
        temp = analyzer.detect_temporal("t", items)
        assert isinstance(cov, list)
        assert isinstance(meth, list)
        assert isinstance(geo, list)
        assert isinstance(temp, list)

    def test_empty_references(self) -> None:
        analyzer = GapAnalyzer()
        report = analyzer.analyze("topic", [])
        assert report.total_references == 0
        assert report.gaps == []

    def test_subtopics_param(self) -> None:
        analyzer = GapAnalyzer(
            {
                "gap_min_sources": 2,
                "gap_min_papers": 1,
                "gap_recency_years": 99,
            }
        )
        items_a = [
            _make_ref(ReferenceSource.pubmed, year=2025, language="en", abstract="In vitro study"),
        ]
        items_b = [
            _make_ref(ReferenceSource.pubmed, year=2025, language="zh", abstract="In vivo study"),
            _make_ref(
                ReferenceSource.openalex, year=2026, language="en", abstract="Clinical trial"
            ),
        ]
        report = analyzer.analyze(
            "topic", items_a + items_b, subtopics={"a": items_a, "b": items_b}
        )
        assert len(report.gaps) == 1
        assert report.gaps[0].topic == "a"

    def test_country_map(self) -> None:
        analyzer = GapAnalyzer()
        items = [_make_ref(language="en")]
        report = analyzer.analyze("topic", items, country_map={"test": "Brazil"})
        assert report.total_references == 1
