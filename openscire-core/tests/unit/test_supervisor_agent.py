# SPDX-License-Identifier: Apache-2.0

"""Tests for SupervisorAgent, state machine, health monitor, conflict resolver,
human handoff, and session persistence."""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock

import pytest
from openscire.agent.conflict import ConflictResolver
from openscire.agent.exceptions import (
    AgentHealthTimeoutError,
    ConflictUnresolvedError,
    HandoffPendingError,
    SupervisorError,
)
from openscire.agent.handoff import HumanHandoff
from openscire.agent.health import AgentHealthMonitor
from openscire.agent.models import (
    AgentPosition,
    ConflictRecord,
    ConflictStatus,
    HandoffStatus,
    HandoffTrigger,
    ResearchPlan,
    ResearchTask,
    SessionState,
    SupervisorState,
    TaskStatus,
)
from openscire.agent.session import SessionManager
from openscire.agent.state import SupervisorStateMachine
from openscire.agent.supervisor import SupervisorAgent

# =========================================================================
# SupervisorStateMachine
# =========================================================================


class TestSupervisorStateMachine:
    def test_initial_state_is_idle(self) -> None:
        sm = SupervisorStateMachine()
        assert sm.state == SupervisorState.idle

    def test_idle_to_planning_valid(self) -> None:
        sm = SupervisorStateMachine()
        sm.transition(SupervisorState.planning)
        assert sm.state == SupervisorState.planning

    def test_idle_to_failed_valid(self) -> None:
        sm = SupervisorStateMachine()
        sm.transition(SupervisorState.failed)
        assert sm.state == SupervisorState.failed

    def test_idle_to_executing_invalid(self) -> None:
        sm = SupervisorStateMachine()
        with pytest.raises(SupervisorError):
            sm.transition(SupervisorState.executing)

    def test_completed_is_terminal(self) -> None:
        sm = SupervisorStateMachine()
        sm.transition(SupervisorState.planning)
        sm.transition(SupervisorState.executing)
        sm.transition(SupervisorState.reviewing)
        sm.transition(SupervisorState.completed)
        assert sm.is_terminal
        assert not sm.is_active

    def test_failed_to_idle_restart(self) -> None:
        sm = SupervisorStateMachine()
        sm.transition(SupervisorState.failed)
        sm.transition(SupervisorState.idle)
        assert sm.state == SupervisorState.idle
        assert sm.can_transition(SupervisorState.planning)

    def test_can_transition_returns_false(self) -> None:
        sm = SupervisorStateMachine()
        assert not sm.can_transition(SupervisorState.reviewing)

    def test_full_lifecycle(self) -> None:
        sm = SupervisorStateMachine()
        assert sm.state == SupervisorState.idle
        sm.transition(SupervisorState.planning)
        sm.transition(SupervisorState.executing)
        sm.transition(SupervisorState.reviewing)
        sm.transition(SupervisorState.completed)
        assert sm.state == SupervisorState.completed
        assert sm.is_terminal

    def test_failed_during_execution(self) -> None:
        sm = SupervisorStateMachine()
        sm.transition(SupervisorState.planning)
        sm.transition(SupervisorState.executing)
        sm.transition(SupervisorState.failed)
        assert sm.state == SupervisorState.failed

    def test_reviewing_retry_to_idle(self) -> None:
        sm = SupervisorStateMachine()
        sm.transition(SupervisorState.planning)
        sm.transition(SupervisorState.executing)
        sm.transition(SupervisorState.reviewing)
        sm.transition(SupervisorState.idle)
        assert sm.state == SupervisorState.idle

    def test_all_valid_transitions(self) -> None:
        expected = {
            (SupervisorState.idle, SupervisorState.planning): True,
            (SupervisorState.idle, SupervisorState.failed): True,
            (SupervisorState.planning, SupervisorState.executing): True,
            (SupervisorState.planning, SupervisorState.failed): True,
            (SupervisorState.executing, SupervisorState.reviewing): True,
            (SupervisorState.executing, SupervisorState.failed): True,
            (SupervisorState.reviewing, SupervisorState.completed): True,
            (SupervisorState.reviewing, SupervisorState.failed): True,
            (SupervisorState.failed, SupervisorState.idle): True,
            (SupervisorState.idle, SupervisorState.executing): False,
            (SupervisorState.planning, SupervisorState.completed): False,
            (SupervisorState.executing, SupervisorState.idle): True,
            (SupervisorState.planning, SupervisorState.idle): True,
            (SupervisorState.completed, SupervisorState.idle): False,
        }
        for (start, target), expected_valid in expected.items():
            sm2 = SupervisorStateMachine(start)
            result = sm2.can_transition(target)
            msg = f"{start.value} -> {target.value}: expected {expected_valid}"
            assert result == expected_valid, msg


# =========================================================================
# AgentHealthMonitor
# =========================================================================


class TestAgentHealthMonitor:
    def test_record_heartbeat_creates_record(self) -> None:
        monitor = AgentHealthMonitor()
        record = monitor.record_heartbeat("agent_a")
        assert record.agent_id == "agent_a"
        assert record.failure_count == 0

    def test_healthy_after_recent_heartbeat(self) -> None:
        monitor = AgentHealthMonitor(heartbeat_timeout=60.0)
        monitor.record_heartbeat("agent_a")
        assert monitor.is_healthy("agent_a") is True

    def test_unhealthy_without_heartbeat(self) -> None:
        monitor = AgentHealthMonitor(heartbeat_timeout=0.0)
        assert monitor.is_healthy("agent_a") is False

    def test_timeout_detection(self) -> None:
        monitor = AgentHealthMonitor(heartbeat_timeout=0.0)
        monitor.record_heartbeat("agent_a")
        timed_out = monitor.check_timeouts()
        assert "agent_a" in timed_out

    def test_no_timeout_within_window(self) -> None:
        monitor = AgentHealthMonitor(heartbeat_timeout=3600.0)
        monitor.record_heartbeat("agent_a")
        timed_out = monitor.check_timeouts()
        assert "agent_a" not in timed_out

    def test_restart_agent_resets_failures(self) -> None:
        monitor = AgentHealthMonitor(heartbeat_timeout=3600.0, max_failures=3)
        monitor.record_heartbeat("agent_a")
        # make agent unhealthy by setting failure count above threshold
        monitor._records["agent_a"].failure_count = 3
        assert not monitor.is_healthy("agent_a")
        monitor.restart_agent("agent_a")
        assert monitor.is_healthy("agent_a") is True

    def test_failed_agents_after_max_failures(self) -> None:
        monitor = AgentHealthMonitor(heartbeat_timeout=0.0, max_failures=2)
        monitor.record_heartbeat("agent_a")
        monitor.check_timeouts()
        assert len(monitor.failed_agents) == 0
        monitor.check_timeouts()
        assert "agent_a" in monitor.failed_agents

    def test_raise_if_unhealthy_raises(self) -> None:
        monitor = AgentHealthMonitor(heartbeat_timeout=0.0)
        with pytest.raises(AgentHealthTimeoutError):
            monitor.raise_if_unhealthy("agent_a")

    def test_raise_if_unhealthy_healthy_ok(self) -> None:
        monitor = AgentHealthMonitor(heartbeat_timeout=3600.0)
        monitor.record_heartbeat("agent_a")
        monitor.raise_if_unhealthy("agent_a")

    def test_list_agents(self) -> None:
        monitor = AgentHealthMonitor()
        monitor.record_heartbeat("a")
        monitor.record_heartbeat("b")
        agents = monitor.list_agents()
        assert "a" in agents
        assert "b" in agents

    def test_get_record_returns_none_for_unknown(self) -> None:
        monitor = AgentHealthMonitor()
        assert monitor.get_record("unknown") is None

    @pytest.mark.asyncio
    async def test_async_timeout_triggers_callback(self) -> None:
        callback = AsyncMock()
        monitor = AgentHealthMonitor(
            heartbeat_timeout=0.0,
            max_failures=1,
            agent_failed_callback=callback,
        )
        monitor.record_heartbeat("agent_a")
        await monitor.check_timeouts_async()
        callback.assert_called_once()


# =========================================================================
# ConflictResolver
# =========================================================================


class TestConflictResolver:
    def test_detect_no_conflicts(self) -> None:
        resolver = ConflictResolver()
        tasks = [
            ResearchTask(task_id="1", agent_role="a", description="Task A"),
            ResearchTask(task_id="2", agent_role="b", description="Task B"),
        ]
        for t in tasks:
            t.status = TaskStatus.completed
            t.result = {"output": {"conclusion": "X is true", "evidence": ["ref1"]}}
        conflicts = resolver.detect(tasks)
        assert len(conflicts) == 0

    def test_detect_contradictory_conclusions(self) -> None:
        resolver = ConflictResolver()
        tasks = [
            ResearchTask(task_id="1", agent_role="agent_a", description="Effect of X on Y"),
            ResearchTask(task_id="2", agent_role="agent_b", description="Effect of X on Y"),
        ]
        for t in tasks:
            t.status = TaskStatus.completed
        tasks[0].result = {"output": {"conclusion": "X increases Y", "evidence": ["ref1"]}}
        tasks[1].result = {"output": {"conclusion": "X does not increase Y", "evidence": ["ref2"]}}
        conflicts = resolver.detect(tasks)
        assert len(conflicts) == 1
        assert conflicts[0].status == ConflictStatus.open

    def test_detect_requires_completed_tasks(self) -> None:
        resolver = ConflictResolver()
        tasks = [
            ResearchTask(task_id="1", agent_role="a", description="Task"),
        ]
        tasks[0].status = TaskStatus.pending
        conflicts = resolver.detect(tasks)
        assert len(conflicts) == 0

    def test_evidence_request_normal(self) -> None:
        resolver = ConflictResolver()
        conflict = resolver._conflicts["c1"] = ConflictRecord(
            conflict_id="c1",
            topic="test",
            positions=[AgentPosition(agent_id="a", claim="X")],
        )
        agents = resolver.request_evidence("c1")
        assert agents == ["a"]
        assert conflict.status == ConflictStatus.evidence_requested

    def test_evidence_request_max_rounds_escalates(self) -> None:
        resolver = ConflictResolver(max_evidence_rounds=1)
        resolver._conflicts["c1"] = ConflictRecord(
            conflict_id="c1",
            topic="test",
            positions=[AgentPosition(agent_id="a", claim="X")],
        )
        resolver.request_evidence("c1")
        agents = resolver.request_evidence("c1")
        assert agents == []
        assert resolver._conflicts["c1"].status == ConflictStatus.escalated_to_human

    def test_escalate_to_human(self) -> None:
        resolver = ConflictResolver()
        resolver._conflicts["c1"] = ConflictRecord(conflict_id="c1", topic="test")
        resolver.escalate_to_human("c1")
        assert resolver._conflicts["c1"].escalated_to_human is True

    def test_resolve(self) -> None:
        resolver = ConflictResolver()
        resolver._conflicts["c1"] = ConflictRecord(conflict_id="c1", topic="test")
        resolver.resolve("c1", "Consensus reached")
        assert resolver._conflicts["c1"].status == ConflictStatus.resolved
        assert resolver._conflicts["c1"].resolution == "Consensus reached"

    def test_register_open_question(self) -> None:
        resolver = ConflictResolver()
        resolver._conflicts["c1"] = ConflictRecord(conflict_id="c1", topic="test")
        resolver.register_open_question("c1")
        assert resolver._conflicts["c1"].status == ConflictStatus.registered_as_open_question

    def test_get_conflict_unknown(self) -> None:
        resolver = ConflictResolver()
        assert resolver.get_conflict("unknown") is None

    def test_open_conflicts_property(self) -> None:
        resolver = ConflictResolver()
        resolver._conflicts["c1"] = ConflictRecord(conflict_id="c1", topic="open")
        resolver._conflicts["c2"] = ConflictRecord(conflict_id="c2", topic="resolved")
        resolver._conflicts["c2"].status = ConflictStatus.resolved
        open_list = resolver.open_conflicts
        assert len(open_list) == 1
        assert open_list[0].conflict_id == "c1"

    def test_unknown_conflict_raises(self) -> None:
        resolver = ConflictResolver()
        with pytest.raises(ConflictUnresolvedError):
            resolver.request_evidence("nonexistent")


# =========================================================================
# HumanHandoff
# =========================================================================


class TestHumanHandoff:
    def test_request_handoff_creates_pending(self) -> None:
        handoff = HumanHandoff()
        req = handoff.request_handoff("Need input", HandoffTrigger.ethical_tier_1)
        assert req.status == HandoffStatus.pending
        assert req.trigger == HandoffTrigger.ethical_tier_1

    def test_has_pending_true(self) -> None:
        handoff = HumanHandoff()
        handoff.request_handoff("test", HandoffTrigger.user_requested)
        assert handoff.has_pending() is True

    def test_has_pending_false(self) -> None:
        handoff = HumanHandoff()
        assert handoff.has_pending() is False

    def test_resolve_handoff(self) -> None:
        handoff = HumanHandoff()
        req = handoff.request_handoff("Need input", HandoffTrigger.ethical_tier_1)
        resolved = handoff.resolve(req.request_id, response={"approved": True})
        assert resolved.status == HandoffStatus.resolved
        assert resolved.response == {"approved": True}
        assert resolved.resolved_at is not None

    @pytest.mark.asyncio
    async def test_wait_for_resolution(self) -> None:
        handoff = HumanHandoff(default_timeout=10.0)
        req = handoff.request_handoff("test", HandoffTrigger.user_requested)

        async def resolve_later() -> None:
            await asyncio.sleep(0.01)
            handoff.resolve(req.request_id, response={"ok": True})

        import asyncio

        asyncio.create_task(resolve_later())
        resolved = await handoff.wait_for_resolution(req.request_id)
        assert resolved.status == HandoffStatus.resolved

    def test_resolve_unknown_raises(self) -> None:
        handoff = HumanHandoff()
        with pytest.raises(HandoffPendingError):
            handoff.resolve("unknown")

    def test_pending_requests_property(self) -> None:
        handoff = HumanHandoff()
        handoff.request_handoff("a", HandoffTrigger.user_requested)
        handoff.request_handoff("b", HandoffTrigger.resource_constraint)
        assert len(handoff.pending_requests) == 2

    def test_resolved_requests_property(self) -> None:
        handoff = HumanHandoff()
        req = handoff.request_handoff("test", HandoffTrigger.user_requested)
        handoff.resolve(req.request_id)
        assert len(handoff.resolved_requests) == 1
        assert len(handoff.pending_requests) == 0

    @pytest.mark.asyncio
    async def test_wait_for_resolution_timeout(self) -> None:
        handoff = HumanHandoff(default_timeout=0.01)
        req = handoff.request_handoff("test", HandoffTrigger.user_requested)
        resolved = await handoff.wait_for_resolution(req.request_id)
        assert resolved.status == HandoffStatus.timed_out


# =========================================================================
# SessionManager
# =========================================================================


class TestSessionManager:
    def test_save_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(storage_dir=tmpdir)
            state = SessionState(
                session_id="test_001",
                supervisor_state=SupervisorState.executing,
            )
            mgr.save(state)
            restored = mgr.restore("test_001")
            assert restored is not None
            assert restored.session_id == "test_001"
            assert restored.supervisor_state == SupervisorState.executing

    def test_restore_nonexistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(storage_dir=tmpdir)
            result = mgr.restore("nonexistent")
            assert result is None

    def test_delete_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(storage_dir=tmpdir)
            state = SessionState(session_id="del_test")
            mgr.save(state)
            assert mgr.delete("del_test") is True

    def test_delete_nonexistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(storage_dir=tmpdir)
            assert mgr.delete("nonexistent") is False

    def test_list_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(storage_dir=tmpdir)
            mgr.save(SessionState(session_id="s1"))
            mgr.save(SessionState(session_id="s2"))
            sessions = mgr.list_sessions()
            assert len(sessions) == 2
            ids = [s["session_id"] for s in sessions]
            assert "s1" in ids
            assert "s2" in ids

    def test_current_session_property(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(storage_dir=tmpdir)
            assert mgr.current_session is None
            state = SessionState(session_id="current_test")
            mgr.save(state)
            assert mgr.current_session is not None
            assert mgr.current_session.session_id == "current_test"


# =========================================================================
# SupervisorAgent (integration-level)
# =========================================================================


@pytest.mark.asyncio
class TestSupervisorAgent:
    async def test_initial_state_is_idle(self) -> None:
        agent = SupervisorAgent()
        assert agent.state == SupervisorState.idle

    async def test_session_id_none_before_start(self) -> None:
        agent = SupervisorAgent()
        assert agent.session_id is None

    async def test_restore_session_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = SupervisorAgent(storage_dir=tmpdir)
            result = agent.restore_session("nonexistent")
            assert result is False

    async def test_save_and_restore_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = SupervisorAgent(storage_dir=tmpdir)
            state = SessionState(session_id="save_test", supervisor_state=SupervisorState.executing)
            agent._session_manager.save(state)
            assert agent.restore_session("save_test") is True
            assert agent.state == SupervisorState.executing

    async def test_stop_cleans_up(self) -> None:
        from openscire.agent.bus import AgentBus

        AgentBus.reset()
        bus = AgentBus.get_bus()
        agent = SupervisorAgent(bus=bus)
        # start session as task and stop quickly
        task = asyncio.create_task(agent.start_session("test question"))
        await asyncio.sleep(0.05)
        agent.stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            task.cancel()
        assert agent.state in (SupervisorState.idle, SupervisorState.failed)

    async def test_conflict_resolver_accessible(self) -> None:
        agent = SupervisorAgent()
        assert agent.conflict_resolver is not None

    async def test_health_monitor_accessible(self) -> None:
        agent = SupervisorAgent()
        assert agent.health_monitor is not None

    async def test_handoff_manager_accessible(self) -> None:
        agent = SupervisorAgent()
        assert agent.handoff_manager is not None

    async def test_session_manager_accessible(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = SupervisorAgent(storage_dir=tmpdir)
            assert agent.session_manager is not None

    async def test_request_and_resolve_handoff(self) -> None:
        agent = SupervisorAgent()
        req = agent.request_handoff("test", HandoffTrigger.ethical_tier_1)
        assert req.status == HandoffStatus.pending
        resolved = agent.resolve_handoff(req.request_id, response={"ok": True})
        assert resolved.status == HandoffStatus.resolved

    async def test_resolve_conflict(self) -> None:
        agent = SupervisorAgent()
        agent.conflict_resolver._conflicts["c1"] = ConflictRecord(
            conflict_id="c1",
            topic="test conflict",
        )
        resolved = agent.resolve_conflict("c1", "Resolved via override")
        assert resolved.status == ConflictStatus.resolved
        assert resolved.resolution == "Resolved via override"

    async def test_generate_default_plan(self) -> None:
        agent = SupervisorAgent()
        plan = await agent._generate_plan("What is the role of X in Y?")
        assert plan is not None
        assert plan.research_question == "What is the role of X in Y?"
        assert len(plan.tasks) > 0

    async def test_ready_tasks_respects_dependencies(self) -> None:
        agent = SupervisorAgent()
        plan = ResearchPlan(
            research_question="test",
            tasks=[
                ResearchTask(task_id="t1", agent_role="a", description="First"),
                ResearchTask(
                    task_id="t2", agent_role="b", description="Second", dependencies=["t1"]
                ),
                ResearchTask(
                    task_id="t3", agent_role="c", description="Third", dependencies=["t1", "t2"]
                ),
            ],
        )
        # No deps met
        ready = agent._get_ready_tasks(plan)
        assert len(ready) == 1
        assert ready[0].task_id == "t1"

        # t1 completed
        plan.tasks[0].status = TaskStatus.completed
        ready = agent._get_ready_tasks(plan)
        assert len(ready) == 1
        assert ready[0].task_id == "t2"

        # t1 + t2 completed
        plan.tasks[1].status = TaskStatus.completed
        ready = agent._get_ready_tasks(plan)
        assert len(ready) == 1
        assert ready[0].task_id == "t3"

    async def test_all_tasks_terminal(self) -> None:
        agent = SupervisorAgent()
        plan = ResearchPlan(
            research_question="test",
            tasks=[
                ResearchTask(task_id="t1", agent_role="a", description="A"),
                ResearchTask(task_id="t2", agent_role="b", description="B"),
            ],
        )
        assert not agent._all_tasks_terminal(plan)
        plan.tasks[0].status = TaskStatus.completed
        plan.tasks[1].status = TaskStatus.failed
        assert agent._all_tasks_terminal(plan)

    async def test_handle_result_updates_task(self) -> None:
        agent = SupervisorAgent()
        from openscire.agent.models import ResultPayload

        agent._plan = ResearchPlan(
            research_question="test",
            tasks=[ResearchTask(task_id="t1", agent_role="a", description="Do X")],
        )
        payload = ResultPayload(task_description="Do X", output={"result": 42}, success=True)
        await agent._handle_result(payload)
        assert agent._plan.tasks[0].status == TaskStatus.completed
        assert agent._plan.tasks[0].result == {"result": 42}

    async def test_handle_result_failure(self) -> None:
        agent = SupervisorAgent()
        agent._plan = ResearchPlan(
            research_question="test",
            tasks=[ResearchTask(task_id="t1", agent_role="a", description="Do X")],
        )
        from openscire.agent.models import ResultPayload

        payload = ResultPayload(task_description="Do X", output={}, success=False, error="Failed")
        await agent._handle_result(payload)
        assert agent._plan.tasks[0].status == TaskStatus.failed
        assert agent._plan.tasks[0].error == "Failed"


# =========================================================================
# End-to-end lifecycle (with mocked bus)
# =========================================================================


@pytest.mark.asyncio
class TestSupervisorAgentLifecycle:
    async def test_full_session_lifecycle(self) -> None:
        from openscire.agent.bus import AgentBus

        AgentBus.reset()
        bus = AgentBus.get_bus()
        agent = SupervisorAgent(bus=bus)

        with tempfile.TemporaryDirectory() as tmpdir:
            agent._session_manager._storage_dir = tmpdir
            task = asyncio.create_task(agent.start_session("Test question"))
            await asyncio.sleep(0.05)
            agent.stop()
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (TimeoutError, asyncio.CancelledError):
                task.cancel()
            assert agent.session_id is not None

    async def test_session_saves_checkpoint(self) -> None:
        from openscire.agent.bus import AgentBus

        AgentBus.reset()
        bus = AgentBus.get_bus()
        agent = SupervisorAgent(bus=bus, storage_dir="/tmp/__test_sessions__")

        os.makedirs("/tmp/__test_sessions__", exist_ok=True)
        task = asyncio.create_task(agent.start_session("Lifecycle test"))
        await asyncio.sleep(0.05)
        agent.stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            task.cancel()
        checkpoints = agent.session_manager.list_sessions()
        assert len(checkpoints) >= 1
