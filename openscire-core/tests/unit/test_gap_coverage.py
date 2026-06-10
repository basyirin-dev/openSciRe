from openscire.references.gap.coverage import CoverageGapDetector
from openscire.references.gap.models import GapType
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


def _make_ref(source: ReferenceSource, keywords: list[str] | None = None) -> ReferenceItem:
    return ReferenceItem(
        id=f"{source.value}-test",
        source=source,
        title="Test",
        keywords=keywords or [],
        authors=[ReferenceAuthor(first="A", last="B")],
    )


class TestCoverageGapDetector:
    def test_sufficient_coverage_no_gap(self) -> None:
        detector = CoverageGapDetector({"gap_min_sources": 2, "gap_min_papers": 1})
        items = [
            _make_ref(ReferenceSource.pubmed),
            _make_ref(ReferenceSource.semantic_scholar),
        ]
        gaps = detector.detect("topic", {"sub": items})
        assert gaps == []

    def test_below_min_sources(self) -> None:
        detector = CoverageGapDetector({"gap_min_sources": 3, "gap_min_papers": 1})
        items = [_make_ref(ReferenceSource.pubmed)]
        gaps = detector.detect("topic", {"sub": items})
        assert len(gaps) == 1
        g = gaps[0]
        assert g.gap_type == GapType.coverage
        assert g.severity == "high"
        assert "sub" in g.topic
        assert "pubmed" in g.details["sources_found"]

    def test_below_min_papers(self) -> None:
        detector = CoverageGapDetector({"gap_min_sources": 1, "gap_min_papers": 10})
        items = [_make_ref(ReferenceSource.pubmed)]
        gaps = detector.detect("topic", {"sub": items})
        assert len(gaps) == 1
        g = gaps[0]
        assert g.gap_type == GapType.coverage
        assert g.severity == "medium"

    def test_multiple_subtopics(self) -> None:
        detector = CoverageGapDetector({"gap_min_sources": 2, "gap_min_papers": 1})
        gaps = detector.detect(
            "topic",
            {
                "good": [
                    _make_ref(ReferenceSource.pubmed),
                    _make_ref(ReferenceSource.openalex),
                ],
                "bad": [_make_ref(ReferenceSource.pubmed)],
            },
        )
        assert len(gaps) == 1
        assert gaps[0].topic == "bad"

    def test_empty_subtopics(self) -> None:
        detector = CoverageGapDetector()
        gaps = detector.detect("topic", {})
        assert gaps == []

    def test_empty_items_in_subtopic(self) -> None:
        detector = CoverageGapDetector()
        gaps = detector.detect("topic", {"sub": []})
        assert gaps == []

    def test_group_by_keywords(self) -> None:
        items = [
            _make_ref(ReferenceSource.pubmed, keywords=["cancer"]),
            _make_ref(ReferenceSource.openalex, keywords=["cancer"]),
            _make_ref(ReferenceSource.semantic_scholar, keywords=["genomics"]),
            _make_ref(ReferenceSource.arxiv, keywords=[]),
        ]
        groups = CoverageGapDetector.group_by_keywords(items)
        assert "cancer" in groups
        assert "genomics" in groups
        assert "uncategorized" in groups
        assert len(groups["cancer"]) == 2
        assert len(groups["genomics"]) == 1
        assert len(groups["uncategorized"]) == 1
