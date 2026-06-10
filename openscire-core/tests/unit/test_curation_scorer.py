from openscire.curation.source_scorer import (
    ConfidenceWeightedRanker,
    SourceQualityScorer,
)
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


def _make_ref(
    title: str = "Test",
    abstract: str = "",
    year: int | None = 2020,
    citation_count: int = 0,
    reproducibility: str = "",
) -> ReferenceItem:
    return ReferenceItem(
        id="test",
        source=ReferenceSource.pubmed,
        title=title,
        abstract=abstract,
        year=year,
        authors=[ReferenceAuthor(first="A", last="B")],
        extra={
            "citation_count": citation_count,
            "reproducibility_status": reproducibility,
        },
    )


class TestSourceQualityScorer:
    def test_meta_analysis_scores_high(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(title="A meta-analysis of treatments")
        score = scorer.score(ref)
        assert score.methodology_score > 0.7

    def test_case_study_scores_low(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(title="A case report of a patient")
        score = scorer.score(ref)
        assert score.methodology_score < 0.4

    def test_no_method_detected(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(title="Some random text")
        score = scorer.score(ref)
        assert score.methodology_score == 0.1

    def test_recency_new(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(year=2026)
        score = scorer.score(ref)
        assert score.recency_score == 1.0

    def test_recency_old(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(year=1990)
        score = scorer.score(ref)
        assert score.recency_score < 0.2

    def test_recency_none(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(year=None)
        score = scorer.score(ref)
        assert score.recency_score == 0.3

    def test_citation_high(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(citation_count=1000)
        score = scorer.score(ref)
        assert score.citation_score > 0.9

    def test_citation_zero(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(citation_count=0)
        score = scorer.score(ref)
        assert score.citation_score == 0.0

    def test_replication_reproduced(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(reproducibility="reproduced")
        score = scorer.score(ref)
        assert score.replication_score == 1.0

    def test_replication_failed(self) -> None:
        scorer = SourceQualityScorer()
        ref = _make_ref(reproducibility="failed_to_reproduce")
        score = scorer.score(ref)
        assert score.replication_score == 0.3


class TestConfidenceWeightedRanker:
    def test_ranks_by_score_descending(self) -> None:
        from openscire.curation.models import SourceQualityScore

        scores = [
            SourceQualityScore(source_id="a", overall_score=0.3),
            SourceQualityScore(source_id="b", overall_score=0.9),
            SourceQualityScore(source_id="c", overall_score=0.5),
        ]
        ranker = ConfidenceWeightedRanker()
        ranked = ranker.rank(scores)
        assert [s.source_id for s in ranked] == ["b", "c", "a"]

    def test_empty_list(self) -> None:
        ranker = ConfidenceWeightedRanker()
        assert ranker.rank([]) == []
