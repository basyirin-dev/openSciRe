# SPDX-License-Identifier: Apache-2.0

"""Tests for FalsificationAgent."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openscire.agent.bus import AgentBus
from openscire.agent.falsification import FalsificationAgent
from openscire.agent.models import (
    AgentMessage,
    MessageType,
    QueryPayload,
    ResultPayload,
    TaskPayload,
)

# ── Helpers ───────────────────────────────────────────────────────────


async def _drain(sleep_s: float = 0.01) -> None:
    await asyncio.sleep(sleep_s)


def _collect_results(
    bus: AgentBus,
    agent_id: str = "supervisor",
) -> list[tuple[str, dict[str, Any], bool, str | None]]:
    """Subscribe to the bus and collect ResultPayload messages."""
    received: list[tuple[str, dict[str, Any], bool, str | None]] = []

    async def _handler(msg: AgentMessage) -> None:
        payload = ResultPayload.model_validate(msg.payload)
        received.append(
            (
                payload.task_description,
                payload.output,
                payload.success,
                payload.error,
            )
        )

    bus.subscribe(agent_id, {MessageType.result}, _handler)
    return received


# ── Fakes ─────────────────────────────────────────────────────────────


class FakeOpenAlexClient:
    def __init__(self) -> None:
        self.search_works_calls: list[dict[str, Any]] = []

    async def search_works(self, query: str, per_page: int = 50) -> Any:  # noqa: ANN401
        self.search_works_calls.append({"query": query, "per_page": per_page})
        return FakeSearchResult(work_ids=["wid1", "wid2"])

    async def fetch_work(self, work_id: str) -> Any:  # noqa: ANN401
        return FakeReferenceItem(
            id=work_id,
            title=f"Paper {work_id}",
            doi=f"10.1234/{work_id}",
            abstract=f"Abstract for {work_id}",
        )


class FakeSearchResult:
    def __init__(self, work_ids: list[str]) -> None:
        self.work_ids = work_ids


class FakeReferenceItem:
    def __init__(
        self,
        id: str = "",
        title: str = "",
        doi: str = "",
        abstract: str = "",
    ) -> None:
        self.id = id
        self.title = title
        self.doi = doi
        self.abstract = abstract


class FakePubMedBridge:
    def __init__(self) -> None:
        self.sync_calls: list[dict[str, Any]] = []

    async def sync(self) -> list[Any]:
        self.sync_calls.append({"synced": True})
        return []


class FakeAdversarialRetriever:
    def __init__(self) -> None:
        self.find_calls: list[list[str]] = []
        self._results: list[Any] = []

    def set_results(self, results: list[Any]) -> None:
        self._results = results

    async def find_contradictory_sources(
        self,
        claims: list[str],
        max_per_claim: int = 3,  # noqa: ARG002
    ) -> list[Any]:  # noqa: ANN401
        self.find_calls.append(claims)
        return self._results


class FakeAdversarialSource:
    def __init__(self, claim: str, title: str = "") -> None:
        self.claim = claim
        self.contradiction_type = "direct_contradiction"
        self.source = {"id": "src1", "title": title or f"Contradicts {claim}"}


class FakeAssumptionMiner:
    def __init__(self) -> None:
        self.extract_calls: list[str] = []
        self._results: list[Any] = []

    def set_results(self, results: list[Any]) -> None:
        self._results = results

    async def extract(self, text: str) -> list[Any]:
        self.extract_calls.append(text)
        return self._results


class FakeAssumption:
    def __init__(self, text: str) -> None:
        self.assumption_text = text
        self.extracted_from = ""
        self.supporting_sources = []
        self.contradicting_sources = []


class FakeQualityScorer:
    def __init__(self) -> None:
        self.score_calls: list[Any] = []

    def score(self, source: Any) -> Any:  # noqa: ANN401
        self.score_calls.append(source)
        return FakeQualityScore(methodology_score=0.8)


class FakeQualityScore:
    def __init__(self, methodology_score: float = 0.8) -> None:
        self.source_id = "src1"
        self.overall_score = 0.75
        self.methodology_score = methodology_score
        self.replication_score = 0.5
        self.citation_score = 0.6
        self.recency_score = 0.7


SAMPLE_HYPOTHESIS = (
    "X protein expression causes increased Y signaling through the Z pathway in cancer cells."
)

SAMPLE_HYPOTHESIS_SIMPLE = "Inhibition of enzyme A increases cognitive performance."


# ── Construction ──────────────────────────────────────────────────────


class TestFalsificationAgentConstruction:
    def test_subscribes_to_task_and_query(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_const_f")

        agent = FalsificationAgent(agent_id="falsification_test", bus=bus)

        assert agent is not None

        async def _test() -> None:
            received: list[MessageType] = []

            async def collector(msg: AgentMessage) -> None:
                received.append(msg.message_type)

            bus.subscribe("test", {MessageType.result, MessageType.response}, collector)

            bus.publish(
                AgentMessage(
                    sender="test",
                    recipient="falsification_test",
                    message_type=MessageType.task,
                    payload=TaskPayload(description="test").model_dump(),
                )
            )
            await _drain()
            bus.publish(
                AgentMessage(
                    sender="test",
                    recipient="falsification_test",
                    message_type=MessageType.query,
                    payload=QueryPayload(question="test").model_dump(),
                )
            )
            await _drain()

            assert collected_types(received) >= {MessageType.result, MessageType.response}

        asyncio.run(_test())
        AgentBus.reset()

    def test_default_agent_id(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_default_f")

        agent = FalsificationAgent(bus=bus)
        assert agent._agent_id == "falsification"

        AgentBus.reset()

    def test_custom_agent_id(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_custom_f")

        agent = FalsificationAgent(agent_id="my_falsifier", bus=bus)
        assert agent._agent_id == "my_falsifier"

        AgentBus.reset()


def collected_types(received: list[MessageType]) -> set[MessageType]:
    return set(received)


# ── Execution ─────────────────────────────────────────────────────────


class TestFalsificationAgentExecution:
    @pytest.fixture(autouse=True)
    def _reset_bus(self) -> None:
        AgentBus.reset()

    @pytest.mark.asyncio
    async def test_handle_task_publishes_result(self) -> None:
        bus = AgentBus.get_bus("test_exec_f")
        FalsificationAgent(bus=bus)
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="falsification",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=SAMPLE_HYPOTHESIS,
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        desc, output, success, error = results[0]
        assert success is True
        assert error is None
        assert "hypothesis" in output
        assert "falsification_search_results" in output

    @pytest.mark.asyncio
    async def test_handle_task_with_parameters(self) -> None:
        bus = AgentBus.get_bus("test_exec_f")
        FalsificationAgent(bus=bus)
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="falsification",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="test task",
                    parameters={"hypothesis": SAMPLE_HYPOTHESIS_SIMPLE},
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        desc, output, success, error = results[0]
        assert success is True
        assert output.get("hypothesis") == SAMPLE_HYPOTHESIS_SIMPLE

    @pytest.mark.asyncio
    async def test_handle_query_returns_response(self) -> None:
        bus = AgentBus.get_bus("test_query_f")
        agent = FalsificationAgent(bus=bus)  # noqa: F841
        received: list[AgentMessage] = []

        async def collector(msg: AgentMessage) -> None:
            received.append(msg)

        bus.subscribe("supervisor", {MessageType.response}, collector)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="falsification",
                message_type=MessageType.query,
                payload=QueryPayload(question="test query").model_dump(),
            )
        )
        await _drain()

        assert len(received) == 1
        assert received[0].message_type == MessageType.response

    @pytest.mark.asyncio
    async def test_handle_task_error_publishes_failure(self) -> None:
        bus = AgentBus.get_bus("test_error_f")
        FalsificationAgent(bus=bus, openalex_client=BrokenClient())
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="falsification",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="",
                    parameters={"hypothesis": "  "},
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        desc, output, success, error = results[0]
        assert success is False
        assert error is not None
        assert "empty hypothesis" in error.lower()

    @pytest.mark.asyncio
    async def test_strips_confidence_from_parameters(self) -> None:
        bus = AgentBus.get_bus("test_exec_f")
        FalsificationAgent(bus=bus, config={"test_mode": True})
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="falsification",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="test",
                    parameters={
                        "hypothesis": SAMPLE_HYPOTHESIS,
                        "confidence": 0.95,
                        "other_data": "some_value",
                    },
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        assert results[0][2] is True
        output = results[0][1]
        assert output.get("hypothesis") == SAMPLE_HYPOTHESIS


class BrokenClient:
    async def search_works(
        self,
        _query: str,  # noqa: ARG002
        _per_page: int = 50,  # noqa: ARG002
    ) -> Any:  # noqa: ANN401
        raise RuntimeError("Bridge unavailable")

    async def fetch_work(self, _work_id: str) -> Any:  # noqa: ANN401, ARG002
        raise RuntimeError("Bridge unavailable")


# ── Pipeline steps ────────────────────────────────────────────────────


class TestFalsificationPipeline:
    """Test individual pipeline steps with hand-rolled fakes."""

    @pytest.mark.asyncio
    async def test_search_with_adversarial_retriever(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        adv = FakeAdversarialRetriever()
        adv.set_results(
            [
                FakeAdversarialSource(claim="X causes Y", title="Contradicting Study"),
            ]
        )
        agent = FalsificationAgent(
            bus=bus,
            adversarial_retriever=adv,
        )
        result = await agent._search_for_falsification(
            SAMPLE_HYPOTHESIS,
            {},
        )

        assert len(adv.find_calls) >= 1
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_search_with_bridges(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        oa = FakeOpenAlexClient()
        agent = FalsificationAgent(
            bus=bus,
            openalex_client=oa,
        )
        await agent._search_for_falsification(
            SAMPLE_HYPOTHESIS,
            {},
        )

        assert len(oa.search_works_calls) >= 1
        assert any("contrary to" in c["query"].lower() for c in oa.search_works_calls)

    @pytest.mark.asyncio
    async def test_search_no_deps(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)
        result = await agent._search_for_falsification(
            SAMPLE_HYPOTHESIS,
            {},
        )
        assert result == []

    def test_generate_counter_examples(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)
        result = agent._generate_counter_examples(SAMPLE_HYPOTHESIS, {})

        assert len(result) >= 1
        for ex in result:
            assert "scenario" in ex
            assert "variable_tested" in ex
            assert "expected_outcome_if_valid" in ex

    def test_generate_counter_examples_simple(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        result = agent._generate_counter_examples("X increases Y", {})

        assert len(result) >= 1
        assert result[0]["variable_tested"] != ""

    def test_generate_counter_examples_empty(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        result = agent._generate_counter_examples("", {})

        assert len(result) >= 1
        for ex in result:
            assert ex["variable_tested"] == "hypothesis"

    def test_extract_variables(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        vars_list = agent._extract_variables(SAMPLE_HYPOTHESIS)

        assert len(vars_list) >= 1
        var_text = " ".join(vars_list).lower()
        assert "protein" in var_text or "signaling" in var_text or "pathway" in var_text

    def test_extract_claims(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        claims = agent._extract_claims(SAMPLE_HYPOTHESIS)

        assert len(claims) >= 1

    @pytest.mark.asyncio
    async def test_identify_confounds_with_miner(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        miner = FakeAssumptionMiner()
        miner.set_results(
            [
                FakeAssumption(text="X is measured without error"),
            ]
        )
        agent = FalsificationAgent(bus=bus, assumption_miner=miner)

        result = await agent._identify_confounds(SAMPLE_HYPOTHESIS, {})

        assert len(miner.extract_calls) >= 1
        assert len(result) >= 1
        assert result[0]["variable"] == "X is measured without error"

    @pytest.mark.asyncio
    async def test_identify_confounds_heuristic(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        hypothesis_with_universal = "All patients show improved response to treatment Y."
        result = await agent._identify_confounds(hypothesis_with_universal, {})

        assert len(result) >= 1
        cats = [r["category"] for r in result]
        assert "selection" in cats

    @pytest.mark.asyncio
    async def test_identify_confounds_causal(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        hypothesis_causal = "Cognitive decline is caused by amyloid beta accumulation."
        result = await agent._identify_confounds(hypothesis_causal, {})

        assert len(result) >= 1
        cats = [r["category"] for r in result]
        assert "mediating" in cats

    def test_generate_alternatives(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        result = agent._generate_alternatives(SAMPLE_HYPOTHESIS, {})

        assert len(result) >= 1
        assert any("reverse" in a.lower() for a in result)
        assert any("common cause" in a.lower() for a in result)

    def test_generate_alternatives_no_variables(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        result = agent._generate_alternatives("", {})

        assert len(result) >= 1
        assert any("reverse" in a.lower() for a in result)

    def test_critique_methodology_no_evidence(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        result = agent._critique_methodology(SAMPLE_HYPOTHESIS, [], {})

        assert "testability_assessment" in result
        assert (
            "unfalsifiable" in result["testability_assessment"].lower()
            or "falsifiable" in result["testability_assessment"].lower()
        )

    def test_critique_methodology_with_evidence(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(
            bus=bus,
            quality_scorer=FakeQualityScorer(),
        )

        evidence = [
            {"source_id": "src1", "title": "Paper 1"},
            {"source_id": "src2", "title": "Paper 2"},
            {"source_id": "src3", "title": "Paper 3"},
        ]
        result = agent._critique_methodology(SAMPLE_HYPOTHESIS, evidence, {})

        assert "n_sources_reviewed" in result
        assert result["n_sources_reviewed"] == 3

    def test_critique_testability(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        testable = "Inhibiting enzyme A reduces metabolite B by 30%."
        untestable = (
            "The invisible force may or may not affect the outcome under certain conditions."
        )

        testable_result = agent._critique_testability(testable)
        assert "testable" in testable_result.lower() or "falsifiable" in testable_result.lower()

        untestable_result = agent._critique_testability(untestable)
        assert (
            "untestable" in untestable_result.lower()
            or "testability" in untestable_result.lower()
            or "hedging" in untestable_result.lower()
        )

    def test_build_report_structure(self) -> None:
        bus = AgentBus.get_bus("test_pipe_f")
        agent = FalsificationAgent(bus=bus)

        report = agent._build_report(
            hypothesis=SAMPLE_HYPOTHESIS,
            contradiction_evidence=[{"source_id": "s1"}],
            counter_examples=[{"scenario": "test"}],
            confounds=[{"variable": "X", "category": "confounding"}],
            alternatives=["Alternative: Z causes both"],
            critique={"testability_assessment": "testable", "n_sources_reviewed": 1},
        )

        expected_keys = {
            "hypothesis",
            "falsification_search_results",
            "counter_examples",
            "confounds",
            "alternative_explanations",
            "methodology_critique",
            "overall_assessment",
            "remaining_uncertainty",
            "suggestions",
            "n_contradicting_sources_found",
            "n_confounds_identified",
            "n_alternatives_proposed",
            "n_counter_examples_generated",
        }
        assert expected_keys.issubset(report.keys())
        assert report["overall_assessment"] == "moderate"


# ── Integration ───────────────────────────────────────────────────────


class TestFalsificationIntegration:
    @pytest.fixture(autouse=True)
    def _reset_bus(self) -> None:
        AgentBus.reset()

    @pytest.mark.asyncio
    async def test_full_pipeline_via_bus(self) -> None:
        bus = AgentBus.get_bus("test_int_f")
        FalsificationAgent(bus=bus, openalex_client=FakeOpenAlexClient())
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="falsification",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=SAMPLE_HYPOTHESIS,
                    parameters={"max_counter_examples": 2, "max_alternatives": 2},
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        _desc, output, success, error = results[0]
        assert success is True
        assert error is None
        assert output["overall_assessment"] in ("weak", "moderate", "strong")
        assert isinstance(output["suggestions"], list)
        assert isinstance(output["falsification_search_results"], list)

    @pytest.mark.asyncio
    async def test_full_pipeline_minimal_deps(self) -> None:
        bus = AgentBus.get_bus("test_int_f")
        FalsificationAgent(bus=bus)
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="falsification",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=SAMPLE_HYPOTHESIS,
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        _desc, output, success, _error = results[0]
        assert success is True
        assert output["falsification_search_results"] == []
        assert len(output["counter_examples"]) >= 1
        assert len(output["alternative_explanations"]) >= 1

    @pytest.mark.asyncio
    async def test_full_pipeline_with_all_deps(self) -> None:
        bus = AgentBus.get_bus("test_int_f")
        adv = FakeAdversarialRetriever()
        adv.set_results([FakeAdversarialSource(claim="X causes Y")])
        miner = FakeAssumptionMiner()
        miner.set_results([FakeAssumption(text="Measurement is precise")])
        scorer = FakeQualityScorer()

        FalsificationAgent(
            bus=bus,
            openalex_client=FakeOpenAlexClient(),
            pubmed_bridge=FakePubMedBridge(),
            adversarial_retriever=adv,
            assumption_miner=miner,
            quality_scorer=scorer,
        )
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="falsification",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=SAMPLE_HYPOTHESIS,
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        output = results[0][1]

        assert len(output["falsification_search_results"]) > 0
        assert len(adv.find_calls) >= 1

        if results[0][2]:
            assert "suggestions" in output

    @pytest.mark.asyncio
    async def test_execute_falsification_empty_hypothesis_raises(self) -> None:
        bus = AgentBus.get_bus("test_int_f")
        agent = FalsificationAgent(bus=bus)

        with pytest.raises(ValueError, match="empty hypothesis"):
            await agent.execute_falsification("  ", {})

    @pytest.mark.asyncio
    async def test_execute_falsification_returns_structured_dict(self) -> None:
        bus = AgentBus.get_bus("test_int_f")
        agent = FalsificationAgent(bus=bus)

        result = await agent.execute_falsification(SAMPLE_HYPOTHESIS, {})

        assert isinstance(result, dict)
        assert result["hypothesis"] == SAMPLE_HYPOTHESIS
        assert "overall_assessment" in result
        assert "suggestions" in result
        assert isinstance(result["counter_examples"], list)
        assert isinstance(result["confounds"], list)
