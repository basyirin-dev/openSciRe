# SPDX-License-Identifier: Apache-2.0

"""SupervisorAgent — orchestrates research sessions via AgentBus.

Manages the full lifecycle:
  idle → planning → executing → reviewing → completed → failed

Delegates task dispatch to specialist agents, monitors health, resolves
conflicts, pauses for human input, persists session state, enforces agent
diversity, detects confabulation, and validates cross-agent citations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from openscire.agent.bus import AgentBus
from openscire.agent.conflict import ConflictResolver
from openscire.agent.diversity import DiversityManager
from openscire.agent.exceptions import (
    SupervisorError,
)
from openscire.agent.handoff import HumanHandoff
from openscire.agent.health import AgentHealthMonitor
from openscire.agent.models import (
    AgentMessage,
    ConflictRecord,
    HandoffRequest,
    HandoffTrigger,
    HeartbeatPayload,
    MessageType,
    ResearchPlan,
    ResearchTask,
    ResultPayload,
    SessionState,
    SupervisorState,
    TaskPayload,
    TaskStatus,
)
from openscire.agent.session import SessionManager
from openscire.agent.state import SupervisorStateMachine


class SupervisorAgent:
    """Orchestrates a research session by managing specialist agents via AgentBus.

    Args:
        agent_id: Unique identifier for this supervisor instance.
        bus: AgentBus instance for message routing.
        provider_factory: Optional async callable that returns a ModelProvider
            for plan generation. Signature: () -> ModelProvider.
        provenance_tracker: Optional tracker for session persistence audit trail.
        heartbeat_timeout: Seconds without heartbeat before agent is considered stalled.
        heartbeat_max_failures: Consecutive timeouts before agent is declared dead.
        storage_dir: Directory for session JSON persistence.
    """

    def __init__(
        self,
        agent_id: str = "supervisor",
        bus: AgentBus | None = None,
        provider_factory: Callable[[], Awaitable[Any]] | None = None,
        provenance_tracker: Any | None = None,  # noqa: ANN401
        heartbeat_timeout: float = 120.0,
        heartbeat_max_failures: int = 3,
        storage_dir: str = ".sessions",
        diversity_manager: DiversityManager | None = None,
        confabulation_detector: Any | None = None,  # noqa: ANN401
        source_enforcer: Any | None = None,  # noqa: ANN401
    ) -> None:
        self._agent_id = agent_id
        self._bus = bus or AgentBus.get_bus()
        self._provider_factory = provider_factory
        self._provenance_tracker = provenance_tracker

        self._state_machine = SupervisorStateMachine()
        self._conflict_resolver = ConflictResolver()
        self._handoff = HumanHandoff()
        self._health_monitor = AgentHealthMonitor(
            heartbeat_timeout=heartbeat_timeout,
            max_failures=heartbeat_max_failures,
            agent_failed_callback=self._on_agent_failed,
        )
        self._session_manager = SessionManager(
            storage_dir=storage_dir,
            provenance_tracker=provenance_tracker,
        )

        self._diversity_manager = diversity_manager
        self._confabulation_detector = confabulation_detector
        self._source_enforcer = source_enforcer

        self._plan: ResearchPlan | None = None
        self._subscriptions: list[Any] = []
        self._session_id: str | None = None
        self._research_context: dict[str, Any] = {}
        self._running = False
        self._diversity_assignments: dict[str, Any] = {}
        self._citation_validations: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_session(
        self,
        research_question: str,
        context: dict[str, Any] | None = None,
        plan: ResearchPlan | None = None,
    ) -> str:
        """Start a new research session from idle.

        Args:
            research_question: The question to investigate.
            context: Optional research context metadata.
            plan: Optional pre-built ResearchPlan. If provided, skips the
                planning phase and executes this plan directly.

        Returns:
            The session ID.

        Raises:
            SupervisorError: If not in idle state.
        """
        if self._state_machine.state != SupervisorState.idle:
            raise SupervisorError(
                message=f"Cannot start session in state {self._state_machine.state.value}",
                source="SupervisorAgent.start_session",
            )

        self._session_id = f"session_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        self._research_context = context or {}
        self._running = True

        self._subscribe()

        self._state_machine.transition(SupervisorState.planning)
        self._save_checkpoint()

        if plan is not None:
            self._plan = plan
        else:
            self._plan = await self._generate_plan(research_question)

        if self._diversity_manager is not None and self._plan is not None:
            roles = list({t.agent_role for t in self._plan.tasks})
            self._diversity_assignments = self._diversity_manager.assign_configs(roles)
            self._research_context["diversity_assignments"] = {
                role: cfg.model_dump() for role, cfg in self._diversity_assignments.items()
            }
            self._save_checkpoint()

        self._state_machine.transition(SupervisorState.executing)
        self._save_checkpoint()

        await self._execute_plan(self._plan)

        return self._session_id

    async def process_message(self, message: AgentMessage) -> None:
        """Handle an incoming message from the bus.

        Registered as a subscription callback during start_session.

        Args:
            message: The incoming AgentMessage.
        """
        if message.message_type == MessageType.heartbeat:
            payload = HeartbeatPayload.model_validate(message.payload)
            self._health_monitor.record_heartbeat(payload.agent_id)

        elif message.message_type == MessageType.result:
            payload = ResultPayload.model_validate(message.payload)
            await self._handle_result(payload)

        elif message.message_type == MessageType.flag:
            await self._handle_flag(message)

    def request_handoff(
        self,
        reason: str,
        trigger: HandoffTrigger,
        context: dict[str, Any] | None = None,
    ) -> HandoffRequest:
        """Request a human handoff. Returns immediately; call
        await_handoff() to block.

        Args:
            reason: Explanation for the handoff.
            trigger: The trigger category.
            context: Additional context for the reviewer.

        Returns:
            The pending HandoffRequest.
        """
        return self._handoff.request_handoff(
            reason=reason,
            trigger=trigger,
            context=context,
        )

    async def await_handoff(self, request_id: str) -> HandoffRequest:
        """Block until a handoff is resolved.

        Args:
            request_id: The handoff to wait for.

        Returns:
            The resolved HandoffRequest.
        """
        return await self._handoff.wait_for_resolution(request_id)

    def resolve_handoff(
        self,
        request_id: str,
        response: dict[str, Any] | None = None,
    ) -> HandoffRequest:
        """Resolve a pending handoff externally.

        Args:
            request_id: The handoff to resolve.
            response: The human response data.

        Returns:
            The resolved HandoffRequest.
        """
        return self._handoff.resolve(request_id, response=response)

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
    ) -> ConflictRecord:
        """Resolve a conflict externally.

        Args:
            conflict_id: The conflict to resolve.
            resolution: Description of the resolution.

        Returns:
            The resolved ConflictRecord.
        """
        return self._conflict_resolver.resolve(conflict_id, resolution)

    def save_session(self) -> str:
        """Persist the current session state.

        Returns:
            The file path of the saved session.
        """
        state = self._build_session_state()
        return self._session_manager.save(state)

    def restore_session(self, session_id: str) -> bool:
        """Restore a previously saved session.

        Returns:
            True if the session was found and restored.
        """
        state = self._session_manager.restore(session_id)
        if state is None:
            return False

        self._session_id = state.session_id
        self._research_context = state.research_context
        self._plan = state.plan
        self._state_machine = SupervisorStateMachine(state.supervisor_state)

        for handoff in state.handoffs:
            if handoff.status.value == "pending":
                self._handoff._pending[handoff.request_id] = handoff

        return True

    def stop(self) -> None:
        """Stop the supervisor and clean up subscriptions."""
        self._running = False
        for sub in self._subscriptions:
            self._bus.unsubscribe(sub)
        self._subscriptions.clear()
        if self._state_machine.is_active:
            self._state_machine.transition(SupervisorState.idle)

    @property
    def state(self) -> SupervisorState:
        return self._state_machine.state

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def plan(self) -> ResearchPlan | None:
        return self._plan

    @property
    def conflict_resolver(self) -> ConflictResolver:
        return self._conflict_resolver

    @property
    def health_monitor(self) -> AgentHealthMonitor:
        return self._health_monitor

    @property
    def handoff_manager(self) -> HumanHandoff:
        return self._handoff

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    # ------------------------------------------------------------------
    # Internal — plan generation
    # ------------------------------------------------------------------

    async def _generate_plan(self, research_question: str) -> ResearchPlan:
        """Decompose a research question into ordered subtasks.

        Uses the ModelProvider if available, otherwise generates a default
        plan structure for common research workflows.
        """
        if self._provider_factory is not None:
            try:
                provider = await self._provider_factory()
                plan_json = await self._ask_llm_for_plan(provider, research_question)
                if plan_json:
                    return ResearchPlan(
                        research_question=research_question,
                        tasks=[ResearchTask(**t) for t in plan_json],
                    )
            except Exception:
                pass

        return self._default_plan(research_question)

    async def _ask_llm_for_plan(
        self,
        provider: Any,  # noqa: ANN401
        research_question: str,
    ) -> list[dict[str, Any]] | None:
        """Ask an LLM to decompose the research question into tasks."""
        prompt = (
            f"Decompose the following research question into a list of subtasks "
            f"for specialist agents. Each task must have: agent_role (one of: "
            f"literature_review, hypothesis_generation, falsification, ethics_review, "
            f"data_analysis, sandbox_execution), description, priority (0-10), "
            f"and dependencies (list of task indices, 0-based).\n\n"
            f"Research question: {research_question}\n\n"
            f"Return a JSON array of task objects."
        )

        messages = [{"role": "user", "content": prompt}]
        response = ""
        async for chunk in provider.stream_chat(messages):
            response += chunk.content if hasattr(chunk, "content") else str(chunk)

        try:
            import json

            tasks = json.loads(response)
            if isinstance(tasks, list):
                for t in tasks:
                    t.setdefault("dependencies", [])
                    t.setdefault("parameters", {})
                return tasks
        except (json.JSONDecodeError, TypeError):
            return None

    def _default_plan(self, research_question: str) -> ResearchPlan:
        """Generate a default research plan for a generic question."""
        return ResearchPlan(
            research_question=research_question,
            tasks=[
                ResearchTask(
                    agent_role="literature_review",
                    description=f"Review literature for: {research_question}",
                    priority=10,
                    dependencies=[],
                ),
                ResearchTask(
                    agent_role="hypothesis_generation",
                    description=f"Generate hypotheses for: {research_question}",
                    priority=5,
                    dependencies=[],  # wired below
                ),
                ResearchTask(
                    agent_role="falsification",
                    description=f"Attempt to falsify hypotheses for: {research_question}",
                    priority=3,
                    dependencies=[],
                ),
                ResearchTask(
                    agent_role="ethics_review",
                    description=f"Ethical review of: {research_question}",
                    priority=8,
                    dependencies=[],
                ),
            ],
        )

    # ------------------------------------------------------------------
    # Internal — execution
    # ------------------------------------------------------------------

    async def _execute_plan(self, plan: ResearchPlan) -> None:
        """Execute all tasks in a plan, respecting dependencies."""
        while self._running:
            ready_tasks = self._get_ready_tasks(plan)
            if not ready_tasks:
                if self._all_tasks_terminal(plan):
                    break
                await asyncio.sleep(0.5)
                continue

            for task in ready_tasks:
                task.status = TaskStatus.in_progress
                self._dispatch_task(task)

            await asyncio.sleep(0.1)

        await self._finalize()

    def _get_ready_tasks(self, plan: ResearchPlan) -> list[ResearchTask]:
        """Get tasks whose dependencies are all completed."""
        ready: list[ResearchTask] = []
        for task in plan.tasks:
            if task.status != TaskStatus.pending:
                continue
            if all(self._is_task_completed(dep_id, plan) for dep_id in task.dependencies):
                task.status = TaskStatus.ready
                ready.append(task)
        ready.sort(key=lambda t: t.priority, reverse=True)
        return ready

    def _is_task_completed(self, task_id: str, plan: ResearchPlan) -> bool:
        for t in plan.tasks:
            if t.task_id == task_id:
                return t.status in (TaskStatus.completed, TaskStatus.skipped)
        return False

    def _all_tasks_terminal(self, plan: ResearchPlan) -> bool:
        return all(
            t.status in (TaskStatus.completed, TaskStatus.failed, TaskStatus.skipped)
            for t in plan.tasks
        )

    def _dispatch_task(self, task: ResearchTask) -> None:
        """Publish a task assignment to the bus.

        Injects diversity assignment (provider, temperature, objective) into
        the task parameters if diversity management is active.
        """
        params = dict(task.parameters)
        if self._diversity_assignments:
            assignment = self._diversity_assignments.get(task.agent_role)
            if assignment is not None:
                params["diversity_provider"] = assignment.provider
                params["diversity_model"] = assignment.model_name
                params["diversity_temperature"] = assignment.temperature
                params["diversity_objective"] = assignment.objective_function

        message = AgentMessage(
            sender=self._agent_id,
            recipient=task.agent_role,
            message_type=MessageType.task,
            payload=TaskPayload(
                description=task.description,
                parameters=params,
            ).model_dump(),
            thread_id=self._session_id,
        )
        self._bus.publish(message)
        task.assigned_message_id = message.message_id

    async def _handle_result(self, payload: ResultPayload) -> None:
        """Process a ResultPayload from a specialist agent.

        Runs confabulation detection and cross-agent citation validation
        on successful results when the respective deps are injected.
        """
        if self._plan is None:
            return

        for task in self._plan.tasks:
            if task.description == payload.task_description:
                if payload.success:
                    task.status = TaskStatus.completed
                    task.result = payload.output
                    await self._check_confabulation(task, payload)
                    await self._validate_citations(task, payload)
                else:
                    task.status = TaskStatus.failed
                    task.error = payload.error
                break

    async def _check_confabulation(
        self,
        task: ResearchTask,
        payload: ResultPayload,
    ) -> None:
        """Run ConfabulationDetector on task result if available.

        Flags and potentially escalates if confabulation is detected.
        """
        if self._confabulation_detector is None:
            return

        output = payload.output
        if not isinstance(output, dict):
            return

        claim_texts = self._extract_claims_from_result(output)
        if not claim_texts:
            return

        try:
            report = self._confabulation_detector.check_claims(
                claim_texts=claim_texts,
                domain=task.agent_role,
            )
            if report.n_flagged > 0:
                flag_details = {
                    "task_id": task.task_id,
                    "agent_role": task.agent_role,
                    "n_flagged": report.n_flagged,
                    "auto_escalated": report.auto_escalated,
                    "flags": [
                        {
                            "text": f.claim_text[:100],
                            "type": f.flag_type.value,
                            "severity": f.severity,
                        }
                        for f in report.flags
                    ],
                }
                self._handoff.request_handoff(
                    reason=(
                        f"Confabulation detected in {task.agent_role}: "
                        f"{report.n_flagged} flagged claims"
                    ),
                    trigger=HandoffTrigger.ethical_tier_1,
                    context=flag_details,
                )

                if self._provenance_tracker is not None:
                    with suppress(Exception):
                        self._provenance_tracker.track(
                            event_type="confabulation_check",
                            data=flag_details,
                        )
        except Exception:
            pass

    def _extract_claims_from_result(self, output: dict[str, Any]) -> list[str]:
        """Extract claim-like text from a result dict.

        Handles common output shapes: 'findings', 'claims', 'synthesis',
        'analysis', 'result', or string values in the dict.
        """
        claims: list[str] = []

        for key in ("findings", "claims", "synthesis", "analysis", "result"):
            val = output.get(key)
            if isinstance(val, str) and len(val) > 20:
                claims.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and len(item) > 20:
                        claims.append(item)

        for val in output.values():
            if isinstance(val, str) and len(val) > 50 and val not in claims:
                claims.append(val)
            if len(claims) >= 10:
                break

        return claims

    async def _validate_citations(
        self,
        task: ResearchTask,
        payload: ResultPayload,
    ) -> None:
        """Trigger cross-agent citation validation if source enforcer available.

        Validates that claims citing sources actually match the source content,
        using a different agent's perspective for independence.
        """
        if self._source_enforcer is None:
            return

        output = payload.output
        if not isinstance(output, dict):
            return

        claim_texts = self._extract_claims_from_result(output)
        if not claim_texts and not output.get("citations"):
            return

        try:
            report = self._source_enforcer.enforce(
                text="\n".join(claim_texts) if claim_texts else str(output),
                known_sources=output.get("sources", []),
            )

            unsupported_count = len(report.unsupported_claims)
            validation_entry = {
                "task_id": task.task_id,
                "agent_role": task.agent_role,
                "n_claims_checked": len(claim_texts),
                "n_verified": report.verified_citations,
                "n_unsupported": unsupported_count,
                "n_retracted": 0,
                "citation_count": len(output.get("citations", [])),
            }
            self._citation_validations.append(validation_entry)

            if self._provenance_tracker is not None:
                with suppress(Exception):
                    self._provenance_tracker.track(
                        event_type="citation_validation",
                        data=validation_entry,
                    )

            if unsupported_count > 0:
                self._handoff.request_handoff(
                    reason=(
                        f"Citation issues in {task.agent_role}: "
                        f"{unsupported_count} unsupported/retracted"
                    ),
                    trigger=HandoffTrigger.unresolved_conflict,
                    context=validation_entry,
                )
        except Exception:
            pass

    async def _handle_flag(self, message: AgentMessage) -> None:
        """Handle a flag message (e.g., ethical concern)."""
        reason = message.payload.get("reason", "Flagged")
        self._handoff.request_handoff(
            reason=reason,
            trigger=HandoffTrigger.ethical_tier_1,
            context=message.payload,
        )

    async def _on_agent_failed(self, agent_id: str, record: Any) -> None:  # noqa: ANN401
        """Callback invoked when an agent exceeds max health failures."""
        self._handoff.request_handoff(
            reason=f"Agent {agent_id} has failed {record.failure_count} times",
            trigger=HandoffTrigger.resource_constraint,
            context={"agent_id": agent_id, "failure_count": record.failure_count},
        )

    # ------------------------------------------------------------------
    # Internal — finalization
    # ------------------------------------------------------------------

    async def _finalize(self) -> None:
        """Transition to reviewing, check for conflicts, then complete or fail."""
        if self._state_machine.state == SupervisorState.executing:
            self._state_machine.transition(SupervisorState.reviewing)

        if self._plan:
            conflicts = self._conflict_resolver.detect(self._plan.tasks)
            if conflicts:
                for conflict in conflicts:
                    self._conflict_resolver.escalate_to_human(conflict.conflict_id)
                    self._handoff.request_handoff(
                        reason=f"Unresolved conflict: {conflict.topic}",
                        trigger=HandoffTrigger.unresolved_conflict,
                        context={"conflict_id": conflict.conflict_id},
                    )

        has_failures = False
        if self._plan:
            has_failures = any(t.status == TaskStatus.failed for t in self._plan.tasks)
            all_done = all(
                t.status in (TaskStatus.completed, TaskStatus.skipped, TaskStatus.failed)
                for t in self._plan.tasks
            )
            if all_done and not has_failures:
                self._state_machine.transition(SupervisorState.completed)
            else:
                self._state_machine.transition(SupervisorState.failed)

        self._save_checkpoint()
        self.stop()

    # ------------------------------------------------------------------
    # Internal — subscriptions
    # ------------------------------------------------------------------

    def _subscribe(self) -> None:
        """Register bus subscriptions for message types the supervisor handles."""
        sub = self._bus.subscribe(
            self._agent_id,
            {MessageType.heartbeat, MessageType.result, MessageType.flag},
            self.process_message,
        )
        self._subscriptions.append(sub)

    # ------------------------------------------------------------------
    # Internal — session persistence
    # ------------------------------------------------------------------

    def _save_checkpoint(self) -> None:
        """Save an intermediate session checkpoint."""
        state = self._build_session_state()
        self._session_manager.save(state)

    def _build_session_state(self) -> SessionState:
        """Build a SessionState from current in-memory state."""
        return SessionState(
            session_id=self._session_id or "unknown",
            research_context=self._research_context,
            supervisor_state=self._state_machine.state,
            plan=self._plan,
            conflicts=self._conflict_resolver.all_conflicts,
            handoffs=self._handoff.resolved_requests + self._handoff.pending_requests,
            heartbeat_records={
                aid: rec
                for aid in self._health_monitor.list_agents()
                for rec in [self._health_monitor.get_record(aid)]
                if rec is not None
            },
        )
