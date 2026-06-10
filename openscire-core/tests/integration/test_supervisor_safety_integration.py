# SPDX-License-Identifier: Apache-2.0

"""Integration tests: SupervisorAgent with diversity, confabulation,
and cross-agent citation validation (Task 6.9).

Verifies that all three safety features work together when injected
into SupervisorAgent.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openscire.agent.bus import AgentBus
from openscire.agent.diversity import DiversityManager
from openscire.agent.models import (
    HandoffTrigger,
    ResearchPlan,
    ResearchTask,
    ResultPayload,
    TaskStatus,
)
from openscire.agent.supervisor import SupervisorAgent
from openscire.models.philosophy import (
    AgentObjective,
)

# =========================================================================
# Fakes for confabulation detector and source enforcer
# =========================================================================


class _FakeFlagType:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeConfabulationDetector:
    """Simulates ConfabulationDetector for integration testing."""

    def __init__(self, n_flagged: int = 0) -> None:
        self.n_flagged = n_flagged
        self.last_claims: list[str] = []
        self.last_domain: str = ""

    def check_claims(
        self,
        claim_texts: list[str],
        sources: Any = None,
        claim_confidences: Any = None,
        domain: str = "",
    ) -> Any:
        self.last_claims = claim_texts
        self.last_domain = domain

        class FakeFlag:
            def __init__(self, text: str) -> None:
                self.claim_text = text
                self.flag_type = _FakeFlagType("no_literature_support")
                self.severity = 0.5

        class FakeReport:
            def __init__(self, n: int) -> None:
                self.total_claims = len(claim_texts) if claim_texts else 0
                self.n_flagged = n
                self.auto_escalated = n > 0
                self.flags = [FakeFlag(c[:100]) for c in (claim_texts or [])] if n > 0 else []

        return FakeReport(self.n_flagged)


class FakeSourceEnforcer:
    """Simulates SourceEnforcer for integration testing."""

    def __init__(
        self,
        verified_citations: int = 0,
        n_unsupported: int = 0,
    ) -> None:
        self.verified_citations = verified_citations
        self.n_unsupported = n_unsupported
        self.last_text: str = ""
        self.last_sources: list[Any] = []

    def enforce(
        self,
        text: str,
        known_sources: list[Any],
        mode: Any = None,
        provider: Any = None,
    ) -> Any:
        self.last_text = text
        self.last_sources = known_sources

        class FakeReport:
            def __init__(self, v: int, u: int) -> None:
                self.verified_citations = v
                self.unverified_citations = 0
                self.unsupported_claims = [
                    {"claim_text": f"unsupported_{i}", "reason": "mock"} for i in range(u)
                ]
                self.cross_check_results = []

        return FakeReport(self.verified_citations, self.n_unsupported)


class FailingConfabulationDetector:
    """A confabulation detector that always raises."""

    def check_claims(
        self,
        claim_texts: list[str],
        sources: Any = None,
        claim_confidences: Any = None,
        domain: str = "",
    ) -> Any:
        raise RuntimeError("Simulated detector failure")


class FailingSourceEnforcer:
    """A source enforcer that always raises."""

    def enforce(
        self,
        text: str,
        known_sources: list[Any],
        mode: Any = None,
        provider: Any = None,
    ) -> Any:
        raise RuntimeError("Simulated enforcer failure")


# =========================================================================
# Helpers
# =========================================================================


def _make_agent(
    diversity_manager: Any = None,
    confabulation_detector: Any = None,
    source_enforcer: Any = None,
) -> SupervisorAgent:
    AgentBus.reset()
    bus = AgentBus.get_bus()
    return SupervisorAgent(
        bus=bus,
        diversity_manager=diversity_manager,
        confabulation_detector=confabulation_detector,
        source_enforcer=source_enforcer,
    )


def _make_plan(
    roles: list[str] | None = None,
) -> ResearchPlan:
    if roles is None:
        roles = ["literature_review", "falsification", "ethics_review"]
    return ResearchPlan(
        research_question="Test integration question?",
        tasks=[
            ResearchTask(
                agent_role=r,
                description=f"Task for {r}",
                priority=5,
                dependencies=[],
            )
            for r in roles
        ],
    )


# =========================================================================
# Diversity integration
# =========================================================================


@pytest.mark.asyncio
class TestDiversityIntegration:
    async def test_diversity_assigned_during_start_session(self) -> None:
        """DiversityManager assigns configs to all roles in the plan."""
        manager = DiversityManager()
        agent = _make_agent(diversity_manager=manager)
        plan = _make_plan()

        task = asyncio.create_task(agent.start_session("test question", plan=plan))
        await asyncio.sleep(0.05)
        agent.stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            pass

        assert "diversity_assignments" in agent._research_context
        assignments = agent._research_context["diversity_assignments"]
        assert set(assignments.keys()) == {"literature_review", "falsification", "ethics_review"}

    async def test_diversity_produces_unique_assignments(self) -> None:
        """All roles get distinct (provider, model, temperature) tuples."""
        manager = DiversityManager()
        agent = _make_agent(diversity_manager=manager)
        plan = _make_plan()

        task = asyncio.create_task(agent.start_session("test", plan=plan))
        await asyncio.sleep(0.05)
        agent.stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            pass

        assignments = agent._research_context["diversity_assignments"]
        tuples = {(a["provider"], a["model_name"], a["temperature"]) for a in assignments.values()}
        assert len(tuples) == 3, f"Got {len(tuples)} unique tuples for 3 roles"

    async def test_diversity_injects_into_task_params(self) -> None:
        """Diversity provider/model/temperature/objective set in research context."""
        AgentBus.reset()
        bus = AgentBus.get_bus()
        manager = DiversityManager()
        agent = _make_agent(diversity_manager=manager)
        plan = _make_plan()

        task = asyncio.create_task(agent.start_session("test", plan=plan))
        await asyncio.sleep(0.1)
        agent.stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            pass

        assignments = agent._research_context.get("diversity_assignments", {})
        for role in ("literature_review", "falsification", "ethics_review"):
            assert role in assignments
            cfg = assignments[role]
            assert "provider" in cfg
            assert "model_name" in cfg
            assert "temperature" in cfg
            assert "objective_function" in cfg

    async def test_diversity_assigns_objective_functions(self) -> None:
        """Objective functions are assigned and cycled across roles."""
        manager = DiversityManager()
        agent = _make_agent(diversity_manager=manager)
        plan = _make_plan()

        task = asyncio.create_task(agent.start_session("test", plan=plan))
        await asyncio.sleep(0.05)
        agent.stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            pass

        assignments = agent._research_context["diversity_assignments"]
        objectives = {a.get("objective_function") for a in assignments.values()}
        valid = {e.value for e in AgentObjective}
        assert objectives.issubset(valid)

    async def test_diversity_no_manager_skips(self) -> None:
        """Without a diversity manager, no assignments are created."""
        agent = _make_agent(diversity_manager=None)
        plan = _make_plan()

        task = asyncio.create_task(agent.start_session("test", plan=plan))
        await asyncio.sleep(0.05)
        agent.stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            pass

        assert "diversity_assignments" not in agent._research_context


# =========================================================================
# Confabulation detection integration
# =========================================================================


@pytest.mark.asyncio
class TestConfabulationIntegration:
    async def test_confabulation_clean_no_handoff(self) -> None:
        """Clean results with no confabulation do not trigger handoff."""
        detector = FakeConfabulationDetector(n_flagged=0)
        agent = _make_agent(confabulation_detector=detector)
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={"findings": "Enzyme X catalyzes ATP synthesis efficiently."},
            success=True,
        )
        await agent._handle_result(payload)

        assert len(agent._handoff.pending_requests) == 0

    async def test_confabulation_flagged_creates_handoff(self) -> None:
        """Flagged confabulation creates a pending handoff."""
        detector = FakeConfabulationDetector(n_flagged=2)
        agent = _make_agent(confabulation_detector=detector)
        plan = _make_plan(roles=["falsification"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for falsification",
            output={
                "claims": [
                    "Claim A is well supported.",
                    "Claim B contradicts known literature.",
                ]
            },
            success=True,
        )
        await agent._handle_result(payload)

        pending = agent._handoff.pending_requests
        assert len(pending) >= 1
        assert "Confabulation" in pending[0].reason
        assert pending[0].trigger == HandoffTrigger.ethical_tier_1

    async def test_confabulation_no_detector_skips(self) -> None:
        """Without a confabulation detector, no handoff is created."""
        agent = _make_agent(confabulation_detector=None)
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={"findings": "Some questionable claim that might be wrong."},
            success=True,
        )
        await agent._handle_result(payload)

        assert len(agent._handoff.pending_requests) == 0

    async def test_confabulation_non_dict_output_skipped(self) -> None:
        """Non-dict-like output is skipped without error."""
        detector = FakeConfabulationDetector(n_flagged=1)
        agent = _make_agent(confabulation_detector=detector)
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={"result": 42},
            success=True,
        )
        await agent._handle_result(payload)

        assert len(agent._handoff.pending_requests) == 0

    async def test_confabulation_failure_does_not_block(self) -> None:
        """A failing detector does not prevent result processing."""
        detector = FailingConfabulationDetector()
        agent = _make_agent(confabulation_detector=detector)
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={"findings": "Important scientific finding."},
            success=True,
        )
        await agent._handle_result(payload)

        assert agent._plan.tasks[0].status == TaskStatus.completed


# =========================================================================
# Citation validation integration
# =========================================================================


@pytest.mark.asyncio
class TestCitationValidationIntegration:
    async def test_citation_validation_records_entry(self) -> None:
        """Successful citation validation stores an entry."""
        enforcer = FakeSourceEnforcer(verified_citations=3, n_unsupported=0)
        agent = _make_agent(source_enforcer=enforcer)
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={
                "findings": "Gene X regulates pathway Y.",
                "citations": ["doi:10.1234/abc"],
            },
            success=True,
        )
        await agent._handle_result(payload)

        assert len(agent._citation_validations) == 1
        entry = agent._citation_validations[0]
        assert entry["n_verified"] == 3
        assert entry["n_unsupported"] == 0
        assert entry["agent_role"] == "literature_review"

    async def test_citation_issues_trigger_handoff(self) -> None:
        """Unsupported citations trigger a handoff."""
        enforcer = FakeSourceEnforcer(verified_citations=1, n_unsupported=2)
        agent = _make_agent(source_enforcer=enforcer)
        plan = _make_plan(roles=["falsification"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for falsification",
            output={
                "findings": "Something with citations.",
                "citations": ["doi:10.9999/madeup"],
            },
            success=True,
        )
        await agent._handle_result(payload)

        pending = agent._handoff.pending_requests
        assert len(pending) >= 1
        assert "Citation" in pending[0].reason
        assert pending[0].trigger == HandoffTrigger.unresolved_conflict

    async def test_citation_no_enforcer_skips(self) -> None:
        """Without a source enforcer, no validation is done."""
        agent = _make_agent(source_enforcer=None)
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={"findings": "Result.", "citations": ["doi:10.1234/abc"]},
            success=True,
        )
        await agent._handle_result(payload)

        assert len(agent._citation_validations) == 0

    async def test_citation_no_claims_no_findings_skipped(self) -> None:
        """Output without claim-like keys skips citation validation."""
        enforcer = FakeSourceEnforcer()
        agent = _make_agent(source_enforcer=enforcer)
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={"result": 42},
            success=True,
        )
        await agent._handle_result(payload)

        assert len(agent._citation_validations) == 0

    async def test_citation_failure_does_not_block(self) -> None:
        """A failing enforcer does not prevent result processing."""
        enforcer = FailingSourceEnforcer()
        agent = _make_agent(source_enforcer=enforcer)
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={"findings": "Important finding.", "citations": ["doi:1"]},
            success=True,
        )
        await agent._handle_result(payload)

        assert agent._plan.tasks[0].status == TaskStatus.completed

    async def test_multiple_validations_accumulate(self) -> None:
        """Multiple results accumulate citation validation entries."""
        enforcer = FakeSourceEnforcer(verified_citations=2, n_unsupported=0)
        agent = _make_agent(source_enforcer=enforcer)
        plan = _make_plan(roles=["literature_review", "falsification"])
        agent._plan = plan

        for i, role in enumerate(["literature_review", "falsification"]):
            payload = ResultPayload(
                task_description=f"Task for {role}",
                output={
                    "findings": f"Finding {i}.",
                    "citations": [f"doi:10.1234/{i}"],
                },
                success=True,
            )
            await agent._handle_result(payload)

        assert len(agent._citation_validations) == 2


# =========================================================================
# Combined integration — all features active
# =========================================================================


@pytest.mark.asyncio
class TestAllSafetyFeaturesCombined:
    async def test_all_features_active_no_issues(self) -> None:
        """All three features active with clean results."""
        manager = DiversityManager()
        detector = FakeConfabulationDetector(n_flagged=0)
        enforcer = FakeSourceEnforcer(verified_citations=2, n_unsupported=0)

        agent = _make_agent(
            diversity_manager=manager,
            confabulation_detector=detector,
            source_enforcer=enforcer,
        )
        plan = _make_plan()

        task = asyncio.create_task(agent.start_session("test all features", plan=plan))
        await asyncio.sleep(0.15)
        agent.stop()
        try:
            await asyncio.wait_for(task, timeout=3.0)
        except (TimeoutError, asyncio.CancelledError):
            pass

        assert len(agent._handoff.pending_requests) == 0
        assert "diversity_assignments" in agent._research_context

    async def test_confabulation_and_citation_issues_both_handoff(self) -> None:
        """Both confabulation and citation issues create separate handoffs."""
        detector = FakeConfabulationDetector(n_flagged=1)
        enforcer = FakeSourceEnforcer(verified_citations=0, n_unsupported=1)

        agent = _make_agent(
            diversity_manager=DiversityManager(),
            confabulation_detector=detector,
            source_enforcer=enforcer,
        )
        plan = _make_plan(roles=["literature_review"])
        agent._plan = plan

        payload = ResultPayload(
            task_description="Task for literature_review",
            output={
                "findings": "Questionable claim with weak support.",
                "citations": ["doi:10.9999/madeup"],
            },
            success=True,
        )
        await agent._handle_result(payload)

        pending = agent._handoff.pending_requests
        assert len(pending) >= 1

        triggers = {r.trigger for r in pending}
        assert HandoffTrigger.ethical_tier_1 in triggers
        assert HandoffTrigger.unresolved_conflict in triggers
