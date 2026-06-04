import pytest
from openscire.curation.adversarial_search import AdversarialSourceRetriever
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


class MockBridge:
    def __init__(self) -> None:
        self.search_calls: list[str] = []

    async def search(self, query: str) -> list[ReferenceItem]:
        self.search_calls.append(query)
        return [
            ReferenceItem(
                id=f"result-{len(self.search_calls)}",
                source=ReferenceSource.pubmed,
                title=f"Result for: {query[:20]}",
                year=2025,
                authors=[ReferenceAuthor(first="A", last="B")],
            ),
        ]


class MockFailingBridge:
    async def search(self, query: str) -> list[ReferenceItem]:
        msg = "Bridge error"
        raise RuntimeError(msg)


@pytest.mark.asyncio
async def test_empty_claims() -> None:
    retriever = AdversarialSourceRetriever()
    results = await retriever.find_contradictory_sources([])
    assert results == []


@pytest.mark.asyncio
async def test_single_claim_with_bridge() -> None:
    bridge = MockBridge()
    retriever = AdversarialSourceRetriever(bridges={"pubmed": bridge})
    results = await retriever.find_contradictory_sources(["Drug X cures disease Y"])
    assert len(results) >= 1
    assert results[0].claim == "Drug X cures disease Y"
    assert results[0].source is not None


@pytest.mark.asyncio
async def test_multiple_claims() -> None:
    bridge = MockBridge()
    retriever = AdversarialSourceRetriever(bridges={"pubmed": bridge})
    results = await retriever.find_contradictory_sources(["Claim A", "Claim B"])
    assert len(results) >= 2


@pytest.mark.asyncio
async def test_bridge_failure_does_not_crash() -> None:
    bridge = MockFailingBridge()
    retriever = AdversarialSourceRetriever(bridges={"failing": bridge})
    results = await retriever.find_contradictory_sources(["Test claim"])
    assert results == []


class TestQueryGeneration:
    def test_contrary_to_generation(self) -> None:
        retriever = AdversarialSourceRetriever()
        queries = retriever._generate_queries("Drug X is effective")
        assert any("contrary to" in q for q in queries)

    def test_negation_insertion(self) -> None:
        retriever = AdversarialSourceRetriever()
        queries = retriever._generate_queries("X causes Y in patients")
        assert any("not" in q for q in queries)

    def test_existing_negation(self) -> None:
        retriever = AdversarialSourceRetriever()
        queries = retriever._generate_queries("X does not cause Y")
        assert len(queries) >= 1
