# SPDX-License-Identifier: Apache-2.0

"""Tests for EthicsAgent (Task 6.5)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openscire.agent.bus import AgentBus
from openscire.agent.ethics_agent import EthicsAgent, EthicsReport
from openscire.agent.models import (
    AgentMessage,
    MessageType,
    QueryPayload,
    TaskPayload,
)
from openscire.constants import RiskTier

# NOTE: openscire.ethics.* and openscire.exceptions.* imports are lazy
# to avoid circular import (logging -> config -> provider -> ethics -> logging).

HYPOTHESIS = "CRISPR gene editing may enhance pathogen virulence"


async def _drain(sleep_s: float = 0.01) -> None:
    await asyncio.sleep(sleep_s)


def _collect_results(
    bus: AgentBus,
    agent_id: str = "supervisor",
) -> list[tuple[str, dict[str, Any], bool, str | None]]:
    received: list[tuple[str, dict[str, Any], bool, str | None]] = []

    async def _handler(msg: AgentMessage) -> None:
        from openscire.agent.models import ResultPayload

        payload = ResultPayload.model_validate(msg.payload)
        received.append((payload.task_description, payload.output, payload.success, payload.error))

    bus.subscribe(agent_id, {MessageType.result}, _handler)
    return received


def _collect_flags(
    bus: AgentBus,
    agent_id: str = "supervisor",
) -> list[dict[str, Any]]:
    received: list[dict[str, Any]] = []

    async def _handler(msg: AgentMessage) -> None:
        received.append(
            {
                "message_type": msg.message_type.value,
                "payload": msg.payload,
            }
        )

    bus.subscribe(
        agent_id,
        {MessageType.flag, MessageType.escalate},
        _handler,
    )
    return received


def _make_tier_result(
    tier: str = "tier_3_low",
    domain: str = "materials_science",
    governance: str = "standard",
    confidence: float = 0.9,
) -> Any:  # noqa: ANN401
    from openscire.ethics.models import TierGovernanceAction, TierResult

    tier_map = {
        "tier_1_high": RiskTier.HIGH,
        "tier_2_medium": RiskTier.MEDIUM,
        "tier_3_low": RiskTier.LOW,
    }
    gov_map = {
        "standard": TierGovernanceAction.STANDARD,
        "human_checkpoint": TierGovernanceAction.HUMAN_CHECKPOINT,
        "cooling_off": TierGovernanceAction.COOLING_OFF,
    }
    return TierResult(
        assigned_tier=tier_map[tier],
        domain=domain,
        governance_action=gov_map[governance],
        confidence=confidence,
    )


# -- Fakes ----------------------------------------------------------------


class FakeFirewall:
    def __init__(
        self,
        decision: Any | None = None,  # noqa: ANN401
        raise_error: Any | None = None,  # noqa: ANN401
    ) -> None:
        if decision is None:
            from openscire.ethics.models import (
                EthicsDecision,
                FirewallAction,
            )

            decision = EthicsDecision(
                decision_id="fw_001",
                overall_action=FirewallAction.FLAG,
            )
        self._decision = decision
        self._raise_error = raise_error
        self.scan_calls: list[tuple[Any, str]] = []

    def scan_prompt(
        self,
        messages: Any,  # noqa: ANN401
        user_id: str = "",
    ) -> Any:  # noqa: ANN401
        self.scan_calls.append((messages, user_id))
        if self._raise_error:
            raise self._raise_error
        return self._decision


class FakeTierClassifier:
    def __init__(
        self,
        result: Any | None = None,  # noqa: ANN401
        raise_error: Exception | None = None,
    ) -> None:
        self._result = result or _make_tier_result()
        self._raise_error = raise_error
        self.classify_calls: list[tuple[str, Any]] = []

    def classify(
        self,
        text: str,
        provenance: Any = None,  # noqa: ANN401
    ) -> Any:  # noqa: ARG002, ANN401
        self.classify_calls.append((text, provenance))
        if self._raise_error:
            raise self._raise_error
        return self._result


class FakeDURCClassifier:
    def __init__(
        self,
        results: list[Any] | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self._results = results or []
        self._raise_error = raise_error
        self.scan_calls: list[tuple[str, Any, Any]] = []

    async def scan(
        self,
        text: str,
        rules: Any,  # noqa: ANN401
        default_action: Any,  # noqa: ANN401
    ) -> list[Any]:  # noqa: ANN401
        self.scan_calls.append((text, rules, default_action))
        if self._raise_error:
            raise self._raise_error
        return self._results


class FakeSovereigntyChecker:
    def __init__(
        self,
        verdict: Any | None = None,  # noqa: ANN401
        raise_error: Exception | None = None,
    ) -> None:
        if verdict is None:
            from openscire.ethics.models import (
                DataOrigin,
                SovereigntyVerdict,
            )

            verdict = SovereigntyVerdict(
                verdict_id="sov_001",
                data_origin=DataOrigin.PUBLIC,
                approved=True,
            )
        self._verdict = verdict
        self._raise_error = raise_error
        self.check_calls: list[tuple[dict[str, Any], Any]] = []

    def check(
        self,
        metadata: dict[str, Any],
        provenance: Any = None,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        self.check_calls.append((metadata, provenance))
        if self._raise_error:
            raise self._raise_error
        return self._verdict


class FakeIndigenousProtector:
    def __init__(self) -> None:
        self.check_calls: list[tuple[dict[str, Any], Any]] = []
        self._verdicts: list[Any] = []

    def add_verdict(self, blocked: bool = False) -> None:
        from openscire.ethics.indigenous_knowledge import (
            IndigenousKnowledgeCategory,
            IndigenousKnowledgeVerdict,
        )

        self._verdicts.append(
            IndigenousKnowledgeVerdict(
                verdict_id=f"ik_{len(self._verdicts)}",
                category=IndigenousKnowledgeCategory.OPEN,
                blocked=blocked,
            )
        )

    def check(
        self,
        metadata: dict[str, Any],
        provenance: Any = None,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        self.check_calls.append((metadata, provenance))
        if self._verdicts:
            return self._verdicts.pop(0)
        from openscire.ethics.indigenous_knowledge import (
            IndigenousKnowledgeCategory,
            IndigenousKnowledgeVerdict,
        )

        return IndigenousKnowledgeVerdict(
            verdict_id="ik_default",
            category=IndigenousKnowledgeCategory.OPEN,
            blocked=False,
        )


class FakeCarbonTracker:
    def __init__(
        self,
        estimate: Any | None = None,  # noqa: ANN401
        raise_error: Exception | None = None,
    ) -> None:
        if estimate is None:
            from openscire.ethics.models import CarbonEstimate

            estimate = CarbonEstimate(
                flops=1e12,
                kwh=0.001,
                co2e_kg=0.0004,
                equivalence_text="equivalent to charging a phone",
            )
        self._estimate = estimate
        self._raise_error = raise_error
        self.estimate_calls: list[tuple[int, int, int]] = []

    def estimate(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_params: int,
    ) -> Any:  # noqa: ANN401
        self.estimate_calls.append(
            (prompt_tokens, completion_tokens, model_params),
        )
        if self._raise_error:
            raise self._raise_error
        return self._estimate


class FakeAuditLog:
    def __init__(self) -> None:
        self.append_calls: list[Any] = []

    def append(
        self,
        entry: Any,  # noqa: ANN401
        signing_key: str = "",  # noqa: ARG002
    ) -> None:
        self.append_calls.append(entry)


# -- Construction ----------------------------------------------------------


class TestEthicsAgentConstruction:
    def test_subscribes_to_task_and_query(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_const_eth")
        EthicsAgent(agent_id="ethics_test", bus=bus)

        async def _test() -> None:
            received: list[MessageType] = []

            async def collector(msg: AgentMessage) -> None:
                received.append(msg.message_type)

            bus.subscribe(
                "test_caller",
                {MessageType.result, MessageType.response},
                collector,
            )
            bus.publish(
                AgentMessage(
                    sender="test_caller",
                    recipient="ethics_test",
                    message_type=MessageType.task,
                    payload=TaskPayload(description="test").model_dump(),
                )
            )
            await _drain()
            bus.publish(
                AgentMessage(
                    sender="test_caller",
                    recipient="ethics_test",
                    message_type=MessageType.query,
                    payload=QueryPayload(question="test").model_dump(),
                )
            )
            await _drain()
            assert MessageType.result in received
            assert MessageType.response in received

        asyncio.run(_test())
        AgentBus.reset()

    def test_default_agent_id(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_default_eth")
        agent = EthicsAgent(bus=bus)
        assert agent._agent_id == "ethics_review"
        AgentBus.reset()

    def test_custom_agent_id(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_custom_eth")
        agent = EthicsAgent(agent_id="my_ethicist", bus=bus)
        assert agent._agent_id == "my_ethicist"
        AgentBus.reset()


# -- Execution -------------------------------------------------------------


class TestEthicsAgentExecution:
    @pytest.mark.asyncio
    async def test_handle_task_publishes_result(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_exec_eth")
        EthicsAgent(bus=bus)
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(description=HYPOTHESIS).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        _, output, success, error = results[0]
        assert success is True
        assert error is None
        assert "hypothesis" in output
        assert "tier_result" in output

    @pytest.mark.asyncio
    async def test_handle_task_with_parameters(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_exec_eth2")
        EthicsAgent(bus=bus)
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="test",
                    parameters={"hypothesis": HYPOTHESIS},
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        _, output, success, _ = results[0]
        assert success is True
        assert output["hypothesis"] == HYPOTHESIS

    @pytest.mark.asyncio
    async def test_handle_query_returns_response(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_query_eth")
        EthicsAgent(bus=bus)
        responses: list[MessageType] = []

        async def collector(msg: AgentMessage) -> None:
            responses.append(msg.message_type)

        bus.subscribe("test_caller", {MessageType.response}, collector)
        bus.publish(
            AgentMessage(
                sender="test_caller",
                recipient="ethics_review",
                message_type=MessageType.query,
                payload=QueryPayload(
                    question="is this ethical?",
                ).model_dump(),
            )
        )
        await _drain()
        assert MessageType.response in responses

    @pytest.mark.asyncio
    async def test_handle_task_error_publishes_failure(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_err_eth")
        EthicsAgent(bus=bus)
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="",
                    parameters={"hypothesis": ""},
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        _, _, success, error = results[0]
        assert success is False
        assert error is not None
        assert "required" in error.lower() or "hypothesis" in error.lower()

    @pytest.mark.asyncio
    async def test_escalation_publishes_flag_and_escalate(
        self,
    ) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_esc_eth")
        tier_result = _make_tier_result(
            tier="tier_1_high",
            domain="virology",
            governance="cooling_off",
            confidence=0.95,
        )
        EthicsAgent(
            bus=bus,
            tier_classifier=FakeTierClassifier(result=tier_result),
        )
        flags = _collect_flags(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=HYPOTHESIS,
                ).model_dump(),
            )
        )
        await _drain(0.05)

        msg_types = {f["message_type"] for f in flags}
        assert "flag" in msg_types
        assert "escalate" in msg_types


# -- Pipeline Steps --------------------------------------------------------


class TestEthicsPipeline:
    @pytest.fixture(autouse=True)
    def _reset_bus(self) -> None:
        AgentBus.reset()

    def test_scan_firewall_clean(self) -> None:
        agent = EthicsAgent(firewall=FakeFirewall())
        result = agent._scan_firewall(HYPOTHESIS)
        assert result["overall_action"] == "flag"
        assert result["governance_blocked"] is False

    def test_scan_firewall_error_mapped(self) -> None:
        from openscire.exceptions.exceptions import EthicsError

        error = EthicsError(
            message="blocked",
            error_code="ETHICS_FIREWALL_BLOCKED",
        )
        agent = EthicsAgent(firewall=FakeFirewall(raise_error=error))
        result = agent._scan_firewall(HYPOTHESIS)
        assert result["overall_action"] == "block"
        assert result["governance_blocked"] is True
        assert "error" in result

    def test_scan_firewall_no_deps(self) -> None:
        agent = EthicsAgent()
        result = agent._scan_firewall(HYPOTHESIS)
        assert result["overall_action"] == "flag"

    def test_classify_tier_low(self) -> None:
        agent = EthicsAgent(tier_classifier=FakeTierClassifier())
        result = agent._classify_tier(HYPOTHESIS)
        assert result["assigned_tier"] == RiskTier.LOW.value
        assert result["governance_action"] == "standard"

    def test_classify_tier_high(self) -> None:
        tier_result = _make_tier_result(
            tier="tier_1_high",
            domain="virology",
            governance="cooling_off",
            confidence=0.95,
        )
        agent = EthicsAgent(
            tier_classifier=FakeTierClassifier(result=tier_result),
        )
        result = agent._classify_tier(HYPOTHESIS)
        assert result["assigned_tier"] == RiskTier.HIGH.value

    def test_classify_tier_medium(self) -> None:
        tier_result = _make_tier_result(
            tier="tier_2_medium",
            domain="clinical_research",
            governance="human_checkpoint",
            confidence=0.8,
        )
        agent = EthicsAgent(
            tier_classifier=FakeTierClassifier(result=tier_result),
        )
        result = agent._classify_tier(HYPOTHESIS)
        assert result["assigned_tier"] == RiskTier.MEDIUM.value
        assert result["governance_action"] == "human_checkpoint"

    def test_classify_tier_no_deps(self) -> None:
        agent = EthicsAgent()
        result = agent._classify_tier(HYPOTHESIS)
        assert result["assigned_tier"] == RiskTier.LOW.value

    @pytest.mark.asyncio
    async def test_flag_dual_use_clean(self) -> None:
        agent = EthicsAgent(durc_classifier=FakeDURCClassifier())
        flags = await agent._flag_dual_use(HYPOTHESIS)
        assert flags == []

    @pytest.mark.asyncio
    async def test_flag_dual_use_triggered(self) -> None:
        from openscire.ethics.models import (
            DURCResult,
            FirewallAction,
            MatchType,
        )

        durc_result = DURCResult(
            triggered=True,
            category="pathogen_enhancement",
            rule_id="r1",
            match_type=MatchType.KEYWORD,
            confidence=0.9,
            action_taken=FirewallAction.WARN,
        )
        agent = EthicsAgent(
            durc_classifier=FakeDURCClassifier(results=[durc_result]),
        )
        flags = await agent._flag_dual_use(HYPOTHESIS)
        assert len(flags) == 1
        assert flags[0]["triggered"] is True

    @pytest.mark.asyncio
    async def test_flag_dual_use_no_deps(self) -> None:
        agent = EthicsAgent()
        flags = await agent._flag_dual_use(HYPOTHESIS)
        assert flags == []

    def test_check_sovereignty_approved(self) -> None:
        agent = EthicsAgent(
            sovereignty_checker=FakeSovereigntyChecker(),
        )
        sv, ik = agent._check_sovereignty(
            [{"data_origin": "public"}],
        )
        assert len(sv) == 1
        assert sv[0]["approved"] is True
        assert ik == []

    def test_check_sovereignty_blocked(self) -> None:
        from openscire.ethics.models import (
            ConsentRestriction,
            DataOrigin,
            SovereigntyVerdict,
        )

        verdict = SovereigntyVerdict(
            verdict_id="sov_blocked",
            data_origin=DataOrigin.INDIGENOUS,
            approved=False,
            requires_human_review=True,
            consent_restrictions=[
                ConsentRestriction.NO_ANALYSIS,
            ],
        )
        agent = EthicsAgent(
            sovereignty_checker=FakeSovereigntyChecker(
                verdict=verdict,
            ),
        )
        sv, ik = agent._check_sovereignty(
            [{"data_origin": "indigenous"}],
        )
        assert len(sv) == 1
        assert sv[0]["approved"] is False

    def test_check_sovereignty_indigenous_blocked(self) -> None:
        protector = FakeIndigenousProtector()
        protector.add_verdict(blocked=True)
        agent = EthicsAgent(indigenous_protector=protector)
        sv, ik = agent._check_sovereignty(
            [{"cultural_restriction": "sacred"}],
        )
        assert len(ik) == 1
        assert ik[0]["blocked"] is True

    def test_check_sovereignty_no_sources(self) -> None:
        agent = EthicsAgent(
            sovereignty_checker=FakeSovereigntyChecker(),
        )
        sv, ik = agent._check_sovereignty([])
        assert sv == []
        assert ik == []

    def test_estimate_carbon_default(self) -> None:
        agent = EthicsAgent(carbon_tracker=FakeCarbonTracker())
        result = agent._estimate_carbon(500, 200, 7_000_000_000)
        assert result["kwh"] > 0
        assert result["co2e_kg"] > 0

    def test_estimate_carbon_no_deps(self) -> None:
        agent = EthicsAgent()
        result = agent._estimate_carbon(500, 200, 7_000_000_000)
        assert result["kwh"] == 0.0

    def test_build_report_structure(self) -> None:
        agent = EthicsAgent()
        report = agent._build_report(
            hypothesis=HYPOTHESIS,
            firewall_decision={"overall_action": "flag"},
            tier_result={"assigned_tier": "tier_3_low"},
            durc_flags=[],
            sovereignty_verdicts=[],
            indigenous_verdicts=[],
            carbon_estimate={"kwh": 0.001, "co2e_kg": 0.0004},
        )
        assert isinstance(report, EthicsReport)
        d = report.model_dict()
        assert d["hypothesis"] == HYPOTHESIS
        assert d["overall_action"] == "pass"
        assert "Estimated carbon cost" in d["recommendations"][-1]

    @pytest.mark.asyncio
    async def test_escalate_tier1_flag_and_escalate(self) -> None:
        bus = AgentBus.get_bus("test_esc_pipe")
        agent = EthicsAgent(bus=bus)
        report = EthicsReport(
            hypothesis=HYPOTHESIS,
            tier_result={
                "assigned_tier": RiskTier.HIGH.value,
                "governance_action": "cooling_off",
            },
        )
        _collect_flags(AgentBus.get_bus("test_esc_pipe"))
        agent._escalate_if_needed(report)
        await _drain(0.01)
        assert report.escalated is True

    def test_escalate_tier3_no_escalation(self) -> None:
        agent = EthicsAgent()
        report = EthicsReport(
            hypothesis=HYPOTHESIS,
            tier_result={
                "assigned_tier": RiskTier.LOW.value,
                "governance_action": "standard",
            },
        )
        agent._escalate_if_needed(report)
        assert report.escalated is False

    @pytest.mark.asyncio
    async def test_escalate_tier2_escalates(self) -> None:
        agent = EthicsAgent()
        report = EthicsReport(
            hypothesis=HYPOTHESIS,
            tier_result={
                "assigned_tier": RiskTier.MEDIUM.value,
                "governance_action": "human_checkpoint",
            },
        )
        agent._escalate_if_needed(report)
        await _drain(0.01)
        assert report.escalated is True

    def test_model_dict_roundtrip(self) -> None:
        report = EthicsReport(
            hypothesis=HYPOTHESIS,
            tier_result={"assigned_tier": "tier_3_low"},
            recommendations=["looks good"],
        )
        d = report.model_dict()
        assert d["hypothesis"] == HYPOTHESIS
        assert "report_id" in d
        assert "timestamp" in d


# -- Integration -----------------------------------------------------------


class TestEthicsIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_via_bus(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_integ_eth")
        tier_result = _make_tier_result(
            tier="tier_3_low",
            domain="materials_science",
            governance="standard",
            confidence=0.9,
        )
        EthicsAgent(
            bus=bus,
            tier_classifier=FakeTierClassifier(result=tier_result),
            sovereignty_checker=FakeSovereigntyChecker(),
            carbon_tracker=FakeCarbonTracker(),
        )
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=HYPOTHESIS,
                ).model_dump(),
            )
        )
        await _drain(0.1)

        assert len(results) == 1
        _, output, success, error = results[0]
        assert success is True
        assert output["hypothesis"] == HYPOTHESIS
        assert output["tier_result"]["assigned_tier"] == RiskTier.LOW.value
        assert output["overall_action"] == "pass"

    @pytest.mark.asyncio
    async def test_full_pipeline_minimal_deps(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_integ_min_eth")
        EthicsAgent(bus=bus)
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=HYPOTHESIS,
                ).model_dump(),
            )
        )
        await _drain(0.1)

        assert len(results) == 1
        _, output, success, _ = results[0]
        assert success is True
        assert output["tier_result"]["assigned_tier"] == RiskTier.LOW.value

    @pytest.mark.asyncio
    async def test_full_pipeline_high_tier_escalates(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_integ_high_eth")
        tier_result = _make_tier_result(
            tier="tier_1_high",
            domain="virology",
            governance="cooling_off",
            confidence=0.95,
        )
        EthicsAgent(
            bus=bus,
            tier_classifier=FakeTierClassifier(result=tier_result),
        )
        results = _collect_results(bus)
        flags = _collect_flags(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=HYPOTHESIS,
                ).model_dump(),
            )
        )
        await _drain(0.1)

        assert len(results) == 1
        _, output, success, _ = results[0]
        assert success is True
        assert output["escalated"] is True
        assert output["overall_action"] == "escalate"
        msg_types = {f["message_type"] for f in flags}
        assert "flag" in msg_types
        assert "escalate" in msg_types

    @pytest.mark.asyncio
    async def test_empty_hypothesis_raises(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_empty_eth")
        EthicsAgent(bus=bus)
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description="",
                    parameters={"hypothesis": ""},
                ).model_dump(),
            )
        )
        await _drain(0.05)

        assert len(results) == 1
        _, _, success, error = results[0]
        assert success is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_full_pipeline_with_data_sources(self) -> None:
        AgentBus.reset()
        bus = AgentBus.get_bus("test_integ_data_eth")
        from openscire.ethics.models import (
            DataOrigin,
            SovereigntyVerdict,
        )

        sovereignty_verdict = SovereigntyVerdict(
            verdict_id="sov_1",
            data_origin=DataOrigin.PUBLIC,
            approved=True,
        )
        EthicsAgent(
            bus=bus,
            sovereignty_checker=FakeSovereigntyChecker(
                verdict=sovereignty_verdict,
            ),
        )
        results = _collect_results(bus)

        bus.publish(
            AgentMessage(
                sender="supervisor",
                recipient="ethics_review",
                message_type=MessageType.task,
                payload=TaskPayload(
                    description=HYPOTHESIS,
                    parameters={
                        "data_sources": [
                            {
                                "data_origin": "public",
                                "source_id": "pubmed_1",
                            },
                        ],
                    },
                ).model_dump(),
            )
        )
        await _drain(0.1)

        assert len(results) == 1
        _, output, success, _ = results[0]
        assert success is True
        assert len(output["sovereignty_verdicts"]) == 1
        assert output["sovereignty_verdicts"][0]["approved"] is True
