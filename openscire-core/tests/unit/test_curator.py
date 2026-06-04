import pytest
from openscire.curation.curator import Curator
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


class MockBridge:
    async def search(self, query: str) -> list[ReferenceItem]:
        return [
            ReferenceItem(
                id="ext1",
                source=ReferenceSource.pubmed,
                title=f"External result for: {query[:20]}",
                year=2025,
                authors=[ReferenceAuthor(first="A", last="B")],
            ),
        ]


def _make_ref(id_str: str, title: str = "Paper") -> ReferenceItem:
    return ReferenceItem(
                id=id_str,
        source=ReferenceSource.pubmed,
                title=title,
        year=2024,
        authors=[ReferenceAuthor(first="A", last="B")],
    )


@pytest.mark.asyncio
async def test_analyze_passes_ratio() -> None:
    curator = Curator(
        config={"min_external_ratio": 0.5},
        bridges={"pubmed": MockBridge()},
    )
    user = [_make_ref("u1"), _make_ref("u2")]
    external = [_make_ref("e1"), _make_ref("e2")]
    report = await curator.analyze(
        research_question="Test question",
        user_sources=user,
        external_sources=external,
    )
    assert report.external_ratio == 0.5
    assert report.external_ratio_pass is True
    assert report.n_user_sources == 2
    assert report.n_external_sources == 2


@pytest.mark.asyncio
async def test_analyze_fails_ratio() -> None:
    curator = Curator(
        config={"min_external_ratio": 0.5},
        bridges={"pubmed": MockBridge()},
    )
    user = [_make_ref("u1"), _make_ref("u2"), _make_ref("u3")]
    external = [_make_ref("e1")]
    report = await curator.analyze(
        research_question="Test",
        user_sources=user,
        external_sources=external,
    )
    assert report.external_ratio_pass is False
    assert report.n_user_sources == 3
    assert report.n_external_sources == 1


@pytest.mark.asyncio
async def test_empty_sources() -> None:
    curator = Curator(bridges={"pubmed": MockBridge()})
    report = await curator.analyze("Question", [], [])
    assert report.n_user_sources == 0
    assert report.n_external_sources == 0
    assert report.external_ratio == 0.0
    assert report.external_ratio_pass is True


@pytest.mark.asyncio
async def test_confidence_ranked_sources() -> None:
    curator = Curator(bridges={"pubmed": MockBridge()})
    user = [_make_ref("u1", "A meta-analysis of everything")]
    external = [_make_ref("e1", "A case report")]
    report = await curator.analyze(
        "Test", user_sources=user, external_sources=external,
    )
    assert len(report.confidence_ranked_sources) == 2
    assert report.confidence_ranked_sources[0].overall_score >= report.confidence_ranked_sources[1].overall_score
