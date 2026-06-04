from openscire.references.gap.geography import GeographicGapDetector
from openscire.references.gap.models import GapType
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


def _make_ref(language: str = "", affiliation: str = "") -> ReferenceItem:
    return ReferenceItem(
        id="test",
        source=ReferenceSource.pubmed,
        title="Test",
        original_language=language,
        authors=[ReferenceAuthor(first="A", last="B", affiliation=affiliation)],
    )


class TestGeographicGapDetector:
    def test_global_north_and_south_no_gap(self) -> None:
        detector = GeographicGapDetector()
        items = [
            _make_ref(language="en"),
            _make_ref(language="zh"),
        ]
        gaps = detector.detect("topic", items)
        assert gaps == []

    def test_all_global_north_flagged_high(self) -> None:
        detector = GeographicGapDetector({"gap_min_global_south": 1})
        items = [
            _make_ref(language="en"),
            _make_ref(language="de"),
            _make_ref(language="fr"),
        ]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
        g = gaps[0]
        assert g.gap_type == GapType.geographic
        assert g.severity == "high"
        assert "Global North" in g.description

    def test_unknown_language_treated_as_en(self) -> None:
        detector = GeographicGapDetector({"gap_min_global_south": 1})
        items = [
            _make_ref(language="en"),
            _make_ref(language="xx"),
        ]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1

    def test_empty_list(self) -> None:
        detector = GeographicGapDetector()
        gaps = detector.detect("topic", [])
        assert gaps == []

    def test_country_map_provides_global_south(self) -> None:
        detector = GeographicGapDetector({"gap_min_global_south": 1})
        items = [_make_ref(language="en")]
        gaps = detector.detect("topic", items, country_map={"test": "Brazil"})
        assert gaps == []

    def test_minimal_global_south_medium_severity(self) -> None:
        detector = GeographicGapDetector({"gap_min_global_south": 2})
        items = [
            _make_ref(language="en"),
            _make_ref(language="zh"),
        ]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
        assert gaps[0].severity == "medium"

    def test_single_item_global_north(self) -> None:
        detector = GeographicGapDetector({"gap_min_global_south": 1})
        items = [_make_ref(language="en")]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
