# SPDX-License-Identifier: Apache-2.0

"""Tests for LiteratureReviewAgent."""

from __future__ import annotations

# ruff: noqa: ARG002, ANN401
import asyncio
from typing import Any

import pytest
from openscire.agent.bus import AgentBus
from openscire.agent.literature_review import LiteratureReviewAgent
from openscire.agent.models import (
    AgentMessage,
    MessageType,
    QueryPayload,
    ResponsePayload,
    ResultPayload,
    TaskPayload,
)

# ── Hand-rolled fakes ────────────────────────────────────────────────


class FakeOpenAlexClient:
    """Minimal fake for OpenAlex client."""

    def __init__(self) -> None:
        self.search_works_calls: list[str] = []

    async def search_works(
        self,
        query: str,
        per_page: int = 25,
        **kwargs: Any,
    ) -> Any:
        self.search_works_calls.append(query)
        return _FakeSearchResult(work_ids=["w1", "w2"])

    async def fetch_work(
        self,
        work_id: str,
    ) -> Any:
        return _make_item(work_id, f"Paper {work_id}", "An abstract about X.", "10.000/{work_id}")


class FakePubMedBridge:
    """Minimal fake for PubMed bridge."""

    def __init__(self) -> None:
        self.sync_called = False

    async def sync(self) -> list[Any]:
        self.sync_called = True
        return [
            _make_item("pmid1", "PubMed Paper 1", "A study about Y.", "10.000/pmid1"),
            _make_item("pmid2", "PubMed Paper 2", "Another Y study.", "10.000/pmid2"),
        ]


class FakeDedupEngine:
    """Minimal fake for DedupEngine."""

    def __init__(self) -> None:
        self.dedup_calls = 0

    def dedup(self, items: list[Any], **kwargs: Any) -> list[Any]:
        self.dedup_calls += 1
        from openscire.references.dedup import DedupResult

        keep = True
        results = []
        for item in items:
            results.append(
                DedupResult(
                    item=item,
                    duplicate_of=None if keep else items[0],
                    confidence=1.0,
                    match_method=None,
                )
            )
            keep = False
        return results


class FakeQualityScorer:
    """Minimal fake for SourceQualityScorer."""

    def __init__(self) -> None:
        self.score_calls = 0

    def score(self, source: Any) -> Any:
        self.score_calls += 1
        from openscire.curation.source_scorer import SourceQualityScore

        return SourceQualityScore(
            source_id=source.id if hasattr(source, "id") else "",
            overall_score=0.85,
            methodology_score=0.9,
            replication_score=0.0,
            citation_score=0.5,
            recency_score=0.8,
        )


class FakeGapAnalyzer:
    """Minimal fake for GapAnalyzer."""

    def __init__(self) -> None:
        self.analyze_calls = 0

    def analyze(self, topic: str, references: list[Any], **kwargs: Any) -> Any:
        self.analyze_calls += 1
        from openscire.references.gap.models import GapReport, LiteratureGap

        return GapReport(
            topic=topic,
            total_references=len(references),
            gaps=[
                LiteratureGap(
                    gap_type="coverage",
                    severity="medium",
                    topic=topic,
                    description="Limited coverage in subtopic X.",
                    recommendation="Search additional databases.",
                ),
            ],
            generated_at="2026-06-08T00:00:00",
        )


class FakeRetractionMonitor:
    """Minimal fake for RetractionMonitor."""

    def __init__(self) -> None:
        self.check_calls: list[str] = []

    async def check_paper(self, doi: str) -> tuple[Any, list[Any]]:
        self.check_calls.append(doi)
        from openscire.references.retraction.models import (  # noqa: I001
            RetractionRecord,
            RetractionSource,
            RetractionStatus,
        )

        if "retracted" in doi:
            return (
                RetractionStatus.retracted,
                [RetractionRecord(identifier=doi, source=RetractionSource.pubmed)],
            )
        return (RetractionStatus.unchecked, [])


class _FakeSearchResult:
    """Minimal fake for OpenAlexSearchResult."""

    def __init__(self, work_ids: list[str]) -> None:
        self.work_ids = work_ids
        self.total_count = len(work_ids)
        self.page = 1
        self.per_page = 25


def _make_item(item_id: str, title: str, abstract: str, doi: str) -> Any:
    from openscire.references.models import ReferenceItem

    return ReferenceItem(
        id=item_id,
        title=title,
        abstract=abstract,
        doi=doi,
        source="openalex",
        year=2025,
        keywords=["test"],
    )


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def reset_bus() -> None:
    AgentBus.reset()
    yield
    AgentBus.reset()


@pytest.fixture
def agent(reset_bus: None) -> LiteratureReviewAgent:  # noqa: ARG001
    return LiteratureReviewAgent(
        agent_id="test_lit_review",
        openalex_client=FakeOpenAlexClient(),
        pubmed_bridge=FakePubMedBridge(),
        dedup_engine=FakeDedupEngine(),
        quality_scorer=FakeQualityScorer(),
        gap_analyzer=FakeGapAnalyzer(),
        retraction_monitor=FakeRetractionMonitor(),
    )


# ── Helpers ──────────────────────────────────────────────────────────


async def _drain(sleep_s: float = 0.02) -> None:
    await asyncio.sleep(sleep_s)


def _collect_results(bus: AgentBus) -> list[AgentMessage]:
    collected: list[AgentMessage] = []

    async def _handler(msg: AgentMessage) -> None:
        collected.append(msg)

    # The agent sends results back to the sender ("supervisor" in tests)
    bus.subscribe("supervisor", {MessageType.result, MessageType.response}, _handler)
    return collected


# ── Tests ────────────────────────────────────────────────────────────


class TestLiteratureReviewAgentConstruction:
    """Agent creation and subscription tests."""

    def test_agent_subscribes_to_task_and_query(self, reset_bus: None) -> None:
        bus = AgentBus.get_bus("test_subs")
        agent = LiteratureReviewAgent(agent_id="sub_test", bus=bus)
        assert agent._agent_id == "sub_test"
        assert agent._sub is not None

    def test_default_agent_id(self, reset_bus: None) -> None:
        agent = LiteratureReviewAgent()
        assert agent._agent_id == "literature_review"


@pytest.mark.asyncio
class TestLiteratureReviewAgentExecution:
    """Full pipeline execution tests."""

    async def test_task_message_triggers_review_and_publishes_result(
        self,
        agent: LiteratureReviewAgent,
    ) -> None:
        bus = agent._bus
        collected = _collect_results(bus)
        await _drain()

        payload = TaskPayload(
            description="What is the effect of X on Y?",
            parameters={"max_results": 20},
        ).model_dump()
        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient=agent._agent_id,
                message_type=MessageType.task,
                payload=payload,
            )
        )
        await _drain(0.1)

        assert len(collected) == 1
        result_msg = collected[0]
        assert result_msg.message_type == MessageType.result
        rp = ResultPayload.model_validate(result_msg.payload)
        assert rp.success is True
        assert "conclusion" in rp.output
        assert rp.output["total_sources_found"] > 0

    async def test_result_contains_evidence_and_confidence(
        self,
        agent: LiteratureReviewAgent,
    ) -> None:
        bus = agent._bus
        collected = _collect_results(bus)
        await _drain()

        payload = TaskPayload(
            description="Impact of climate change on biodiversity",
        ).model_dump()
        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient=agent._agent_id,
                message_type=MessageType.task,
                payload=payload,
            )
        )
        await _drain(0.1)

        assert len(collected) == 1
        rp = ResultPayload.model_validate(collected[0].payload)
        assert len(rp.output["evidence"]) > 0
        assert rp.output["confidence"] > 0.0

    async def test_query_message_responds(self, agent: LiteratureReviewAgent) -> None:
        bus = agent._bus
        await _drain()

        responses: list[AgentMessage] = []

        async def handler(msg: AgentMessage) -> None:
            responses.append(msg)

        bus.subscribe("supervisor", {MessageType.response}, handler)
        await _drain()

        payload = QueryPayload(question="Summarize findings on X.").model_dump()
        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient=agent._agent_id,
                message_type=MessageType.query,
                payload=payload,
            )
        )
        await _drain(0.1)

        assert len(responses) == 1
        rp = ResponsePayload.model_validate(responses[0].payload)
        assert "received query" in rp.content
        assert rp.confidence == 0.0

    async def test_error_during_review_publishes_failure(
        self,
        reset_bus: None,
    ) -> None:
        bus = AgentBus.get_bus("test_error")
        agent = LiteratureReviewAgent(
            agent_id="failing_agent",
            bus=bus,
            openalex_client=None,
        )
        collected: list[AgentMessage] = []

        async def handler(msg: AgentMessage) -> None:
            collected.append(msg)

        bus.subscribe("supervisor", {MessageType.result}, handler)
        await _drain()

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient=agent._agent_id,
                message_type=MessageType.task,
                # empty dict to trigger TaskPayload validation error
                payload={},
            )
        )
        await _drain(0.1)

        assert len(collected) == 1
        rp = ResultPayload.model_validate(collected[0].payload)
        assert rp.success is False


@pytest.mark.asyncio
class TestLiteratureReviewPipeline:
    """Individual pipeline step tests."""

    async def test_decompose_query_splits_on_and(self) -> None:
        agent = LiteratureReviewAgent()
        result = agent._decompose_query("Effect of X on Y and role of Z")
        assert len(result) >= 2

    async def test_decompose_query_returns_full_question(self) -> None:
        agent = LiteratureReviewAgent()
        result = agent._decompose_query("What is the effect of X on Y?")
        assert len(result) == 1

    async def test_search_openalex_returns_items(self) -> None:
        agent = LiteratureReviewAgent(openalex_client=FakeOpenAlexClient())
        items = await agent._search_openalex(["test query"], {})
        assert len(items) > 0
        assert hasattr(items[0], "id")

    async def test_search_pubmed_returns_items(self) -> None:
        agent = LiteratureReviewAgent(pubmed_bridge=FakePubMedBridge())
        items = await agent._search_pubmed(["test query"], {})
        assert len(items) == 2

    async def test_search_with_no_client_returns_empty(self) -> None:
        agent = LiteratureReviewAgent()
        items = await agent._search_openalex(["test"], {})
        assert items == []

    async def test_dedup_removes_duplicates(self) -> None:
        dedup = FakeDedupEngine()
        agent = LiteratureReviewAgent(dedup_engine=dedup)
        items = [
            _make_item("a", "Same", "Abstract A.", "10.000/a"),
            _make_item("b", "Same", "Abstract B.", "10.000/b"),
        ]
        result = agent._deduplicate(items)
        assert len(result) == 1

    async def test_dedup_with_no_engine_returns_original(self) -> None:
        agent = LiteratureReviewAgent()
        items = [_make_item("a", "Paper", "Abstract.", "10.000/a")]
        result = agent._deduplicate(items)
        assert result == items

    async def test_synthesize_returns_conclusion_and_confidence(self) -> None:
        agent = LiteratureReviewAgent()
        items = [_make_item("a", "Paper A", "Abstract of A.", "10.000/a")]
        scores = []
        result = agent._synthesize("Test question", items, scores)
        assert "conclusion" in result
        assert "confidence" in result
        assert result["confidence"] >= 0.0

    async def test_synthesize_empty_items(self) -> None:
        agent = LiteratureReviewAgent()
        result = agent._synthesize("Test", [], [])
        assert "No literature found" in result["conclusion"]
        assert result["confidence"] == 0.0

    async def test_assess_quality_returns_scores(self) -> None:
        scorer = FakeQualityScorer()
        agent = LiteratureReviewAgent(quality_scorer=scorer)
        items = [_make_item("a", "Paper A", "Abstract.", "10.000/a")]
        scores = agent._assess_quality(items)
        assert len(scores) == 1
        assert scores[0].overall_score > 0.0

    async def test_assess_quality_no_scorer_returns_empty(self) -> None:
        agent = LiteratureReviewAgent()
        items = [_make_item("a", "Paper", "Abstract.", "10.000/a")]
        scores = agent._assess_quality(items)
        assert scores == []

    async def test_identify_gaps_returns_report(self) -> None:
        agent = LiteratureReviewAgent(gap_analyzer=FakeGapAnalyzer())
        items = [_make_item("a", "Paper", "Abstract.", "10.000/a")]
        report = agent._identify_gaps("Test topic", items)
        assert "gaps" in report

    async def test_identify_gaps_no_analyzer(self) -> None:
        agent = LiteratureReviewAgent()
        items = [_make_item("a", "Paper", "Abstract.", "10.000/a")]
        report = agent._identify_gaps("Test topic", items)
        assert report == {}

    async def test_detect_contradictions_finds_conflicts(self) -> None:
        agent = LiteratureReviewAgent()
        items = [
            _make_item("a", "X increases Y", "X clearly increases Y in all cases.", "10.000/a"),
            _make_item("b", "X does not increase Y", "X has no effect on Y.", "10.000/b"),
        ]
        conflicts = agent._detect_contradictions(items)
        assert len(conflicts) == 1

    async def test_detect_contradictions_no_false_positives(self) -> None:
        agent = LiteratureReviewAgent()
        items = [
            _make_item("a", "X increases Y", "X increases Y in all cases.", "10.000/a"),
            _make_item("b", "Z increases W", "Z shows strong effect on W.", "10.000/b"),
        ]
        conflicts = agent._detect_contradictions(items)
        assert len(conflicts) == 0

    async def test_check_retractions_detects_retracted(self) -> None:
        monitor = FakeRetractionMonitor()
        agent = LiteratureReviewAgent(retraction_monitor=monitor)
        items = [
            _make_item("a", "Retracted Paper", "Bad science.", "10.000/retracted-paper"),
            _make_item("b", "Clean Paper", "Good science.", "10.000/clean"),
        ]
        warnings = await agent._check_retractions(items)
        assert len(warnings) >= 1
        assert any("retracted" in w["doi"] for w in warnings)

    async def test_check_retractions_no_monitor(self) -> None:
        agent = LiteratureReviewAgent()
        items = [_make_item("a", "Paper", "Abstract.", "10.000/a")]
        warnings = await agent._check_retractions(items)
        assert warnings == []

    async def test_rank_evidence_returns_top_items(self) -> None:
        scorer = FakeQualityScorer()
        agent = LiteratureReviewAgent(quality_scorer=scorer)
        items = [
            _make_item("a", "Paper A", "Abstract.", "10.000/a"),
            _make_item("b", "Paper B", "Abstract.", "10.000/b"),
            _make_item("c", "Paper C", "Abstract.", "10.000/c"),
        ]
        scores = agent._assess_quality(items)
        ranked = agent._rank_evidence(items, scores, top_n=2)
        assert len(ranked) == 2
        assert all("id" in r and "quality_score" in r for r in ranked)


@pytest.mark.asyncio
class TestLiteratureReviewIntegration:
    """Integration-level tests with full pipeline."""

    async def test_full_pipeline_via_bus(self, agent: LiteratureReviewAgent) -> None:
        bus = agent._bus
        collected: list[AgentMessage] = []

        async def handler(msg: AgentMessage) -> None:
            collected.append(msg)

        bus.subscribe("supervisor", {MessageType.result}, handler)
        await _drain()

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient=agent._agent_id,
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="What is the effect of X on Y?",
                    parameters={"max_results": 10},
                ).model_dump(),
            )
        )
        await _drain(0.2)

        assert len(collected) == 1
        rp = ResultPayload.model_validate(collected[0].payload)
        assert rp.success
        assert rp.output["total_sources_found"] > 0
        assert rp.output["unique_sources"] > 0
        assert len(rp.output["sub_queries_used"]) >= 1

    async def test_pipeline_with_missing_dependencies(
        self,
        reset_bus: None,
    ) -> None:
        bus = AgentBus.get_bus("minimal")
        agent = LiteratureReviewAgent(
            agent_id="minimal",
            bus=bus,
            openalex_client=None,
            pubmed_bridge=None,
            dedup_engine=None,
            quality_scorer=None,
            gap_analyzer=None,
            retraction_monitor=None,
        )
        collected: list[AgentMessage] = []

        async def handler(msg: AgentMessage) -> None:
            collected.append(msg)

        bus.subscribe("supervisor", {MessageType.result}, handler)
        await _drain()

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient=agent._agent_id,
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="Test question",
                    parameters={},
                ).model_dump(),
            )
        )
        await _drain(0.1)

        assert len(collected) == 1
        rp = ResultPayload.model_validate(collected[0].payload)
        assert rp.success
        assert rp.output["total_sources_found"] == 0
