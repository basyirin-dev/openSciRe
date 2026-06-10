from openscire.curation.models import (
    AdversarialSource,
    Assumption,
    EchoChamberReport,
    SourceProvenance,
    SourceQualityScore,
)
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


class TestSourceProvenance:
    def test_values(self) -> None:
        assert SourceProvenance.user_provided == "user_provided"
        assert SourceProvenance.externally_retrieved == "externally_retrieved"


class TestAdversarialSource:
    def test_defaults(self) -> None:
        s = AdversarialSource()
        assert s.claim == ""
        assert s.source is None
        assert s.contradiction_type == ""
        assert s.confidence == 0.0

    def test_with_source(self) -> None:
        ref = ReferenceItem(
            id="r1",
            source=ReferenceSource.pubmed,
            title="Test",
            authors=[ReferenceAuthor(first="A", last="B")],
        )
        s = AdversarialSource(
            claim="claim",
            source=ref,
            contradiction_type="direct",
            retrieved_via="pubmed",
            confidence=0.8,
        )
        assert s.claim == "claim"
        assert s.source is not None
        assert s.source.id == "r1"


class TestAssumption:
    def test_defaults(self) -> None:
        a = Assumption(assumption_text="test")
        assert a.extracted_from == ""
        assert a.supporting_sources == []
        assert a.contradicting_sources == []


class TestSourceQualityScore:
    def test_defaults(self) -> None:
        s = SourceQualityScore(source_id="s1")
        assert s.overall_score == 0.0
        assert s.methodology_score == 0.0


class TestEchoChamberReport:
    def test_defaults(self) -> None:
        r = EchoChamberReport()
        assert r.external_ratio == 0.0
        assert r.n_user_sources == 0
        assert r.generated_at is not None

    def test_with_values(self) -> None:
        r = EchoChamberReport(
            external_ratio=0.6,
            external_ratio_pass=True,
            n_user_sources=2,
            n_external_sources=3,
        )
        assert r.external_ratio == 0.6
        assert r.n_user_sources == 2
        assert r.n_external_sources == 3
