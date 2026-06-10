# SPDX-License-Identifier: Apache-2.0

"""Workflow orchestration layer — predefined templates, custom workflows,
progress tracking, and provenance recording.

Provides:
    - WorkflowTemplate (3 predefined research workflows)
    - WorkflowBuilder (fluent API for custom pipelines)
    - WorkflowOrchestrator (execution, status, provenance)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from openscire.agent.bus import AgentBus
from openscire.agent.models import (
    ResearchPlan,
    ResearchTask,
    SupervisorState,
    TaskStatus,
)
from openscire.agent.supervisor import SupervisorAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkflowTemplate(StrEnum):
    """Predefined workflow templates."""

    LITERATURE_TO_FALSIFICATION = "literature_to_falsification"
    HYPOTHESIS_FULL_CYCLE = "hypothesis_full_cycle"
    CONTRADICTION_DETECTION = "contradiction_detection"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class WorkflowStep(BaseModel):
    """A single step in a workflow definition."""

    step_id: str
    agent_role: str
    description: str
    parameters: dict[str, Any] = {}
    dependencies: list[str] = []
    priority: int = 5


class WorkflowDefinition(BaseModel):
    """A complete workflow composed of ordered steps with dependencies."""

    workflow_id: str = ""
    name: str = ""
    description: str = ""
    steps: list[WorkflowStep] = []

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        if not self.workflow_id:
            self.workflow_id = str(uuid.uuid4())


class WorkflowStepStatus(BaseModel):
    """Runtime status of a single workflow step."""

    step_id: str
    status: TaskStatus = TaskStatus.pending
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class WorkflowStatus(BaseModel):
    """Runtime status of an entire workflow execution."""

    workflow_id: str
    name: str = ""
    state: SupervisorState = SupervisorState.idle
    steps: list[WorkflowStepStatus] = []
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowProgress(BaseModel):
    """Externally consumable progress snapshot for a running workflow."""

    workflow_id: str
    name: str = ""
    progress_pct: float = 0.0
    completed: int = 0
    total: int = 0
    current_step: str | None = None
    bottleneck: str | None = None
    state: SupervisorState = SupervisorState.idle


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

_TEMPLATE_STEPS: dict[str, list[dict[str, Any]]] = {
    WorkflowTemplate.LITERATURE_TO_FALSIFICATION: [
        {
            "step_id": "lit_review",
            "agent_role": "literature_review",
            "description": "Review existing literature on the research question",
            "priority": 10,
            "dependencies": [],
        },
        {
            "step_id": "gap_identification",
            "agent_role": "literature_review",
            "description": "Identify gaps and contradictions in the literature",
            "priority": 7,
            "dependencies": ["lit_review"],
        },
        {
            "step_id": "hypothesis_gen",
            "agent_role": "hypothesis_generation",
            "description": "Generate hypotheses addressing identified gaps",
            "priority": 5,
            "dependencies": ["gap_identification"],
        },
        {
            "step_id": "falsification",
            "agent_role": "falsification",
            "description": "Attempt to falsify the generated hypotheses",
            "priority": 3,
            "dependencies": ["hypothesis_gen"],
        },
        {
            "step_id": "ethics_review",
            "agent_role": "ethics_review",
            "description": "Ethical review of hypothesis and falsification results",
            "priority": 8,
            "dependencies": ["falsification"],
        },
        {
            "step_id": "report",
            "agent_role": "literature_review",
            "description": "Compile final research report",
            "priority": 1,
            "dependencies": ["ethics_review"],
        },
    ],
    WorkflowTemplate.HYPOTHESIS_FULL_CYCLE: [
        {
            "step_id": "hypothesis_gen",
            "agent_role": "hypothesis_generation",
            "description": "Generate hypotheses from the research question",
            "priority": 10,
            "dependencies": [],
        },
        {
            "step_id": "experimental_design",
            "agent_role": "data_analysis",
            "description": "Design experimental protocol to test hypotheses",
            "priority": 7,
            "dependencies": ["hypothesis_gen"],
        },
        {
            "step_id": "ethics_review",
            "agent_role": "ethics_review",
            "description": "Ethical review of experimental design",
            "priority": 8,
            "dependencies": ["experimental_design"],
        },
        {
            "step_id": "falsification",
            "agent_role": "falsification",
            "description": "Execute falsification attempt on hypotheses",
            "priority": 5,
            "dependencies": ["ethics_review"],
        },
        {
            "step_id": "negative_result_registration",
            "agent_role": "data_analysis",
            "description": "Register negative results from falsification",
            "priority": 3,
            "dependencies": ["falsification"],
        },
    ],
    WorkflowTemplate.CONTRADICTION_DETECTION: [
        {
            "step_id": "lit_search",
            "agent_role": "literature_review",
            "description": "Search literature for relevant publications",
            "priority": 10,
            "dependencies": [],
        },
        {
            "step_id": "contradiction_detection",
            "agent_role": "falsification",
            "description": "Find contradictions between sources",
            "priority": 8,
            "dependencies": [],
        },
        {
            "step_id": "alternative_hypothesis_gen",
            "agent_role": "hypothesis_generation",
            "description": "Generate alternative hypotheses from contradictions",
            "priority": 5,
            "dependencies": ["lit_search", "contradiction_detection"],
        },
        {
            "step_id": "review",
            "agent_role": "ethics_review",
            "description": "Review alternative hypotheses",
            "priority": 3,
            "dependencies": ["alternative_hypothesis_gen"],
        },
    ],
}


def list_templates() -> list[str]:
    """Return names of all available workflow templates."""
    return list(_TEMPLATE_STEPS)


def get_template(name: str) -> WorkflowDefinition:
    """Return a WorkflowDefinition for the named template.

    Raises:
        ValueError: If the template name is unknown.
    """
    raw = _TEMPLATE_STEPS.get(name)
    if raw is None:
        valid = ", ".join(sorted(_TEMPLATE_STEPS))
        raise ValueError(f"Unknown template '{name}'. Available: {valid}")
    return WorkflowDefinition(
        name=name,
        description=_template_description(name),
        steps=[WorkflowStep(**s) for s in raw],
    )


def _template_description(name: str) -> str:
    descs = {
        WorkflowTemplate.LITERATURE_TO_FALSIFICATION: (
            "Literature review -> gap identification -> hypothesis generation -> "
            "falsification attempt -> ethics review -> final report"
        ),
        WorkflowTemplate.HYPOTHESIS_FULL_CYCLE: (
            "Hypothesis generation -> experimental design -> ethics review -> "
            "falsification -> negative result registration"
        ),
        WorkflowTemplate.CONTRADICTION_DETECTION: (
            "Parallel literature search + contradiction detection -> "
            "alternative hypothesis generation -> review"
        ),
    }
    return descs.get(name, "")


# ---------------------------------------------------------------------------
# WorkflowBuilder
# ---------------------------------------------------------------------------


class WorkflowBuilder:
    """Fluent builder for constructing custom WorkflowDefinitions.

    Usage:
        builder = WorkflowBuilder("My Pipeline", "Custom agent chain")
        builder.step("literature_review", "Gather papers", deps=[])
        builder.step("falsification", "Test hypothesis", deps=["lit_review"])
        wf = builder.build()
    """

    def __init__(
        self,
        name: str = "",
        description: str = "",
    ) -> None:
        self._name = name
        self._description = description
        self._steps: list[WorkflowStep] = []

    def step(
        self,
        agent_role: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        step_id: str | None = None,
        priority: int = 5,
    ) -> WorkflowBuilder:
        """Add a step to the workflow.

        Args:
            agent_role: Which agent type handles this step.
            description: Human-readable description of the step.
            parameters: Task parameters passed to the agent.
            dependencies: List of step_ids this step depends on.
            step_id: Explicit step ID (auto-generated if omitted).
            priority: Execution priority (higher = sooner).

        Returns:
            Self for chaining.
        """
        sid = step_id or f"step_{len(self._steps) + 1}"
        self._steps.append(
            WorkflowStep(
                step_id=sid,
                agent_role=agent_role,
                description=description,
                parameters=parameters or {},
                dependencies=dependencies or [],
                priority=priority,
            )
        )
        return self

    def build(self) -> WorkflowDefinition:
        """Build and return the WorkflowDefinition."""
        return WorkflowDefinition(
            name=self._name,
            description=self._description,
            steps=list(self._steps),
        )


# ---------------------------------------------------------------------------
# CPM Bottleneck Detection
# ---------------------------------------------------------------------------


def _compute_critical_path_length(
    steps: list[WorkflowStep],
    status_map: dict[str, TaskStatus],
) -> dict[str, int]:
    """Compute the longest remaining path length from each step.

    Uses reverse topological order. A completed/skipped step has path
    length 0 (it no longer blocks anything).
    """
    successors: dict[str, list[str]] = {s.step_id: [] for s in steps}
    for s in steps:
        for dep in s.dependencies:
            successors.setdefault(dep, []).append(s.step_id)

    path_lengths: dict[str, int] = {}

    def _length(node: str) -> int:
        if node in path_lengths:
            return path_lengths[node]
        status = status_map.get(node, TaskStatus.pending)
        if status in (TaskStatus.completed, TaskStatus.skipped, TaskStatus.failed):
            path_lengths[node] = 0
            return 0
        max_succ = 0
        for succ in successors.get(node, []):
            max_succ = max(max_succ, 1 + _length(succ))
        path_lengths[node] = max_succ
        return max_succ

    for s in steps:
        _length(s.step_id)

    return path_lengths


# ---------------------------------------------------------------------------
# WorkflowOrchestrator
# ---------------------------------------------------------------------------


class WorkflowOrchestrator:
    """Orchestrates workflow execution by injecting plans into SupervisorAgent.

    Args:
        bus: AgentBus instance for message routing.
        provenance_tracker: Optional tracker for workflow-level provenance.
    """

    def __init__(
        self,
        bus: AgentBus | None = None,
        provenance_tracker: Any | None = None,  # noqa: ANN401
    ) -> None:
        self._bus = bus or AgentBus.get_bus("workflow_orchestrator")
        self._provenance_tracker = provenance_tracker
        self._workflows: dict[str, WorkflowStatus] = {}
        self._supervisors: dict[str, SupervisorAgent] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        definition: WorkflowDefinition,
        research_question: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Execute a workflow definition.

        Spawns a SupervisorAgent with an injected plan derived from the
        workflow definition. Returns immediately with the workflow_id;
        call wait_for_completion() to block until done.

        Args:
            definition: The workflow to execute.
            research_question: The question to investigate.
            context: Optional research context.

        Returns:
            The workflow_id for status tracking.
        """
        workflow_id = definition.workflow_id
        started_at = datetime.now(UTC)

        self._workflows[workflow_id] = WorkflowStatus(
            workflow_id=workflow_id,
            name=definition.name,
            state=SupervisorState.executing,
            steps=[WorkflowStepStatus(step_id=s.step_id) for s in definition.steps],
            started_at=started_at,
        )

        bg_task = asyncio.create_task(
            self._execute_workflow(
                workflow_id=workflow_id,
                definition=definition,
                research_question=research_question,
                context=context or {},
                started_at=started_at,
            )
        )
        bg_task.add_done_callback(self._on_workflow_done)
        self._tasks[workflow_id] = bg_task

        return workflow_id

    async def wait_for_completion(
        self,
        workflow_id: str,
        timeout: float | None = None,
    ) -> WorkflowStatus:
        """Block until a workflow completes.

        Args:
            workflow_id: The workflow to wait for.
            timeout: Optional timeout in seconds.

        Returns:
            The final WorkflowStatus.

        Raises:
            TimeoutError: If timeout is reached before completion.
            KeyError: If workflow_id is unknown.
        """
        task = self._tasks.get(workflow_id)
        if task is None:
            raise KeyError(f"Unknown workflow: {workflow_id}")
        await asyncio.wait_for(task, timeout=timeout)
        return self._workflows[workflow_id]

    def get_status(self, workflow_id: str) -> WorkflowStatus | None:
        """Get the current status of a workflow."""
        return self._workflows.get(workflow_id)

    def get_progress(self, workflow_id: str) -> WorkflowProgress | None:
        """Get a lightweight progress snapshot of a workflow."""
        status = self._workflows.get(workflow_id)
        if status is None:
            return None

        total = len(status.steps)
        completed = sum(1 for s in status.steps if s.status == TaskStatus.completed)
        progress_pct = (completed / total * 100) if total > 0 else 0.0

        current_step = None
        for s in status.steps:
            if s.status == TaskStatus.in_progress:
                current_step = s.step_id
                break

        bottleneck = self._compute_bottleneck(status.steps)

        return WorkflowProgress(
            workflow_id=workflow_id,
            name=status.name,
            progress_pct=round(progress_pct, 1),
            completed=completed,
            total=total,
            current_step=current_step,
            bottleneck=bottleneck,
            state=status.state,
        )

    def list_workflows(self) -> list[WorkflowStatus]:
        """Return status of all tracked workflows."""
        return list(self._workflows.values())

    @staticmethod
    def list_templates() -> list[str]:
        """Return names of all available workflow templates."""
        return list_templates()

    @staticmethod
    def get_template(name: str) -> WorkflowDefinition:
        """Return a WorkflowDefinition for the named template."""
        return get_template(name)

    @staticmethod
    def create_builder(
        name: str = "",
        description: str = "",
    ) -> WorkflowBuilder:
        """Create a WorkflowBuilder for custom workflows."""
        return WorkflowBuilder(name=name, description=description)

    # ------------------------------------------------------------------
    # Internal — execution
    # ------------------------------------------------------------------

    async def _execute_workflow(
        self,
        workflow_id: str,
        definition: WorkflowDefinition,
        research_question: str,
        context: dict[str, Any],
        started_at: datetime,  # noqa: ARG002
    ) -> None:
        """Run the workflow inside a SupervisorAgent.

        This runs as a background asyncio.Task. On success or failure,
        the WorkflowStatus is updated accordingly.
        """
        self._record_provenance(
            workflow_id,
            "workflow_started",
            {
                "name": definition.name,
                "question": research_question,
                "step_count": len(definition.steps),
            },
        )

        plan = self._build_plan(definition, research_question)

        supervisor = SupervisorAgent(
            bus=self._bus,
            provenance_tracker=self._provenance_tracker,
        )
        self._supervisors[workflow_id] = supervisor

        try:
            await supervisor.start_session(
                research_question=research_question,
                context=context,
                plan=plan,
            )

            self._update_status_from_supervisor(workflow_id, supervisor)
            wf_status = self._workflows[workflow_id]
            wf_status.state = supervisor.state
            wf_status.completed_at = datetime.now(UTC)

            state_label = supervisor.state.value
            self._record_provenance(
                workflow_id,
                f"workflow_{state_label}",
                {
                    "state": state_label,
                    "total_steps": len(definition.steps),
                },
            )

        except asyncio.CancelledError:
            wf_status = self._workflows.get(workflow_id)
            if wf_status:
                wf_status.state = SupervisorState.failed
                wf_status.error = "Workflow cancelled"
                wf_status.completed_at = datetime.now(UTC)
            self._record_provenance(
                workflow_id,
                "workflow_cancelled",
                {},
            )
            raise

        except Exception as exc:
            logger.exception("Workflow %s failed: %s", workflow_id, exc)
            wf_status = self._workflows.get(workflow_id)
            if wf_status:
                wf_status.state = SupervisorState.failed
                wf_status.error = str(exc)
                wf_status.completed_at = datetime.now(UTC)
            self._update_status_from_supervisor(workflow_id, supervisor)
            self._record_provenance(
                workflow_id,
                "workflow_failed",
                {"error": str(exc)},
            )

    def _on_workflow_done(self, _task: asyncio.Task[None]) -> None:
        """Callback when a background workflow task completes."""
        pass  # Status already updated in _execute_workflow

    # ------------------------------------------------------------------
    # Internal — plan building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_plan(
        definition: WorkflowDefinition,
        research_question: str,
    ) -> ResearchPlan:
        """Convert a WorkflowDefinition into a ResearchPlan.

        Step IDs become task IDs for reliable matching.
        """
        tasks = [
            ResearchTask(
                task_id=step.step_id,
                agent_role=step.agent_role,
                description=step.description,
                parameters=dict(step.parameters),
                dependencies=list(step.dependencies),
                priority=step.priority,
            )
            for step in definition.steps
        ]
        return ResearchPlan(
            research_question=research_question,
            tasks=tasks,
        )

    # ------------------------------------------------------------------
    # Internal — status tracking
    # ------------------------------------------------------------------

    def _update_status_from_supervisor(
        self,
        workflow_id: str,
        supervisor: SupervisorAgent,
    ) -> None:
        """Sync workflow step statuses from the supervisor's plan."""
        wf_status = self._workflows.get(workflow_id)
        if wf_status is None:
            return

        plan = supervisor.plan
        if plan is None:
            return

        task_map = {t.task_id: t for t in plan.tasks}
        for step_status in wf_status.steps:
            task = task_map.get(step_status.step_id)
            if task is None:
                continue
            step_status.status = task.status
            step_status.result = task.result
            step_status.error = task.error

    def _compute_bottleneck(
        self,
        step_statuses: list[WorkflowStepStatus],
    ) -> str | None:
        """Find the pending step blocking the longest dependency chain."""
        pending = [s.step_id for s in step_statuses if s.status == TaskStatus.pending]
        if not pending:
            return None

        steps = [
            WorkflowStep(
                step_id=s.step_id,
                agent_role="",
                description="",
                dependencies=[],
            )
            for s in step_statuses
        ]
        status_map = {s.step_id: s.status for s in step_statuses}
        path_lengths = _compute_critical_path_length(steps, status_map)

        best = max(pending, key=lambda sid: path_lengths.get(sid, 0))
        return best if path_lengths.get(best, 0) > 0 else None

    # ------------------------------------------------------------------
    # Internal — provenance
    # ------------------------------------------------------------------

    def _record_provenance(
        self,
        workflow_id: str,
        event: str,
        data: dict[str, Any],
    ) -> None:
        """Record a workflow-level provenance entry.

        Failures are logged but never raised.
        """
        if self._provenance_tracker is None:
            return
        try:
            self._provenance_tracker.track(
                action_type=f"workflow.{event}",
                agent_id=f"workflow_orchestrator.{workflow_id[:8]}",
                details={
                    "workflow_id": workflow_id,
                    **data,
                },
            )
        except Exception:
            logger.exception(
                "Failed to record workflow provenance: %s/%s",
                workflow_id,
                event,
            )
