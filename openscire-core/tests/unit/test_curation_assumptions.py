import pytest
from openscire.curation.assumption_miner import AssumptionMiner, AssumptionTester
from openscire.references.models import ReferenceAuthor, ReferenceItem, ReferenceSource


class MockBridge:
    async def search(self, query: str) -> list[ReferenceItem]:
        return [
            ReferenceItem(
                id="r1",
                source=ReferenceSource.pubmed,
                title="Testing the assumption",
                abstract="This study tests the assumption that",
                year=2025,
                authors=[ReferenceAuthor(first="A", last="B")],
            ),
        ]


class TestAssumptionMiner:
    def test_empty_question(self) -> None:
        miner = AssumptionMiner()
        assert miner.extract("") == []

    def test_marker_detection(self) -> None:
        miner = AssumptionMiner()
        result = miner.extract("Assuming that gene X is essential, what happens?")
        assert len(result) >= 1
        assert "assuming" in result[0].assumption_text.lower()

    def test_given_that_marker(self) -> None:
        miner = AssumptionMiner()
        result = miner.extract("Given that the model is correct, predict the outcome.")
        assert len(result) >= 1

    def test_fallback_no_markers(self) -> None:
        miner = AssumptionMiner()
        result = miner.extract("What is the effect of temperature on reaction rate?")
        assert len(result) >= 1

    def test_multiple_assumptions(self) -> None:
        miner = AssumptionMiner()
        result = miner.extract("Assuming X is true, and given that Y holds, what about Z?")
        assert len(result) >= 2


@pytest.mark.asyncio
async def test_assumption_tester() -> None:
    from openscire.curation.models import Assumption

    bridge = MockBridge()
    tester = AssumptionTester(bridges={"pubmed": bridge})
    assumptions = [Assumption(assumption_text="gene X is essential")]
    tested = await tester.test(assumptions)
    assert len(tested) == 1
    assert len(tested[0].supporting_sources) > 0 or len(tested[0].contradicting_sources) > 0


@pytest.mark.asyncio
async def test_assumption_tester_empty() -> None:
    tester = AssumptionTester()
    result = await tester.test([])
    assert result == []
