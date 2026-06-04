from openscire.references.gap.methodology import MethodologicalMonocultureDetector
from openscire.references.gap.models import GapType
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


def _make_ref(title: str = "", abstract: str = "") -> ReferenceItem:
    return ReferenceItem(
        id="test",
        source=ReferenceSource.pubmed,
        title=title,
        abstract=abstract,
        authors=[ReferenceAuthor(first="A", last="B")],
    )


class TestMethodologicalMonocultureDetector:
    def test_multiple_methods_no_gap(self) -> None:
        detector = MethodologicalMonocultureDetector({"gap_min_method_categories": 2})
        items = [
            _make_ref(title="In vitro study of cells"),
            _make_ref(title="Clinical trial phase II"),
        ]
        gaps = detector.detect("topic", items)
        assert gaps == []

    def test_single_method_monoculture(self) -> None:
        detector = MethodologicalMonocultureDetector({"gap_min_method_categories": 2})
        items = [
            _make_ref(title="In vitro cell culture assay"),
            _make_ref(title="Cell line experiments"),
        ]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
        g = gaps[0]
        assert g.gap_type == GapType.methodological_monoculture
        assert g.severity == "high"
        assert "in vitro" in g.details["methods_found"]

    def test_no_methods_detected(self) -> None:
        detector = MethodologicalMonocultureDetector()
        items = [
            _make_ref(title="A study of things", abstract="Some results were found."),
            _make_ref(title="Another study", abstract="More findings."),
        ]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
        assert gaps[0].severity == "medium"
        assert gaps[0].details["n_methods_detected"] == 0

    def test_single_item_no_gap(self) -> None:
        detector = MethodologicalMonocultureDetector()
        items = [_make_ref(title="In vitro study")]
        gaps = detector.detect("topic", items)
        assert gaps == []

    def test_empty_list(self) -> None:
        detector = MethodologicalMonocultureDetector()
        gaps = detector.detect("topic", [])
        assert gaps == []

    def test_abstract_based_detection(self) -> None:
        detector = MethodologicalMonocultureDetector({"gap_min_method_categories": 2})
        items = [
            _make_ref(abstract="We performed an observational cohort study"),
            _make_ref(abstract="We developed a computational model"),
        ]
        gaps = detector.detect("topic", items)
        assert gaps == []

    def test_boundary_two_categories(self) -> None:
        detector = MethodologicalMonocultureDetector({"gap_min_method_categories": 3})
        items = [
            _make_ref(title="In vitro study"),
            _make_ref(title="In vivo mouse model"),
        ]
        gaps = detector.detect("topic", items)
        assert len(gaps) == 1
        assert gaps[0].severity == "medium"
