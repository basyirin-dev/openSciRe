from openscire.references.gap.models import GapType
from openscire.references.gap.temporal import TemporalGapDetector
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


def _make_ref(year: int | None) -> ReferenceItem:
    return ReferenceItem(
        id="test",
        source=ReferenceSource.pubmed,
        title="Test",
        year=year,
        authors=[ReferenceAuthor(first="A", last="B")],
    )


class TestTemporalGapDetector:
    def test_no_gap_continuous(self) -> None:
        detector = TemporalGapDetector({"gap_min_gap_years": 2, "gap_recency_years": 6})
        items = [_make_ref(2020), _make_ref(2021), _make_ref(2022)]
        gaps = detector.detect("topic", items)
        assert gaps == []

    def test_finds_gap_of_3_years(self) -> None:
        detector = TemporalGapDetector({"gap_min_gap_years": 2, "gap_recency_years": 99})
        items = [_make_ref(2020), _make_ref(2023)]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
        g = gaps[0]
        assert g.gap_type == GapType.temporal
        assert g.severity == "medium"
        assert g.details["gap_start"] == 2020
        assert g.details["gap_end"] == 2023

    def test_large_gap_5_years_high_severity(self) -> None:
        detector = TemporalGapDetector({"gap_min_gap_years": 2, "gap_recency_years": 99})
        items = [_make_ref(2010), _make_ref(2016)]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
        assert gaps[0].severity == "high"
        assert gaps[0].details["gap_duration"] == 6

    def test_gap_just_below_threshold(self) -> None:
        detector = TemporalGapDetector({"gap_min_gap_years": 2, "gap_recency_years": 99})
        items = [_make_ref(2020), _make_ref(2021)]
        gaps = detector.detect("topic", items)
        assert gaps == []

    def test_recency_gap(self) -> None:
        detector = TemporalGapDetector({"gap_min_gap_years": 99, "gap_recency_years": 3})
        items = [_make_ref(2020), _make_ref(2021)]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
        g = gaps[0]
        assert g.gap_type == GapType.temporal
        assert g.details["recency_gap"] >= 5

    def test_empty_list(self) -> None:
        detector = TemporalGapDetector()
        gaps = detector.detect("topic", [])
        assert gaps == []

    def test_single_item(self) -> None:
        detector = TemporalGapDetector()
        items = [_make_ref(2020)]
        gaps = detector.detect("topic", items)
        assert gaps == []

    def test_none_years(self) -> None:
        detector = TemporalGapDetector()
        items = [_make_ref(None), _make_ref(None)]
        gaps = detector.detect("topic", items)
        assert gaps == []

    def test_multiple_gaps(self) -> None:
        detector = TemporalGapDetector({"gap_min_gap_years": 2, "gap_recency_years": 99})
        items = [_make_ref(2000), _make_ref(2005), _make_ref(2010)]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 2
