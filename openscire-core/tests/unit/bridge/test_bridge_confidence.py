import pytest
from openscire.bridge.confidence import ConfidenceTrace, PropagationStrategy


class TestConfidenceTrace:
    def test_union_max(self) -> None:
        root = ConfidenceTrace(
            value=0.0,
            source="root",
            children=[
                ConfidenceTrace(value=0.3, source="a"),
                ConfidenceTrace(value=0.9, source="b"),
                ConfidenceTrace(value=0.5, source="c"),
            ],
        )
        result = root.propagate(PropagationStrategy.UNION)
        assert result.value == 0.9

    def test_intersection_min(self) -> None:
        root = ConfidenceTrace(
            value=0.0,
            source="root",
            children=[
                ConfidenceTrace(value=0.3, source="a"),
                ConfidenceTrace(value=0.9, source="b"),
                ConfidenceTrace(value=0.5, source="c"),
            ],
        )
        result = root.propagate(PropagationStrategy.INTERSECTION)
        assert result.value == 0.3

    def test_weighted_average(self) -> None:
        root = ConfidenceTrace(
            value=0.0,
            source="root",
            children=[
                ConfidenceTrace(value=1.0, source="a", weight=2.0),
                ConfidenceTrace(value=0.0, source="b", weight=1.0),
            ],
        )
        result = root.propagate(PropagationStrategy.WEIGHTED_AVERAGE)
        assert result.value == pytest.approx(0.666667, rel=1e-5)

    def test_single_child(self) -> None:
        child = ConfidenceTrace(value=0.8, source="single")
        root = ConfidenceTrace(value=0.0, source="root", children=[child])
        result = root.propagate(PropagationStrategy.UNION)
        assert result.value == 0.8

    def test_empty_children(self) -> None:
        leaf = ConfidenceTrace(value=0.7, source="leaf")
        result = leaf.propagate(PropagationStrategy.UNION)
        assert result.value == 0.7

    def test_deep_nesting(self) -> None:
        grandchild_a = ConfidenceTrace(value=0.9, source="gc_a")
        grandchild_b = ConfidenceTrace(value=0.3, source="gc_b")
        child = ConfidenceTrace(
            value=0.0,
            source="child",
            children=[grandchild_a, grandchild_b],
        )
        root = ConfidenceTrace(
            value=0.0,
            source="root",
            children=[child],
        )
        result = root.propagate(PropagationStrategy.UNION)
        assert result.value == 0.9

    def test_propagate_returns_copy(self) -> None:
        child = ConfidenceTrace(value=0.5, source="child")
        root = ConfidenceTrace(value=0.0, source="root", children=[child])
        result = root.propagate(PropagationStrategy.UNION)
        assert result is not root
        assert result.children[0] is not child
