# SPDX-License-Identifier: Apache-2.0

"""Agent message models — MessageType, AgentMessage, AgentThread, typed payload helpers."""

import uuid
from datetime import UTC, datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(StrEnum):
    """Enumeration of all agent message types."""

    query = "query"
    response = "response"
    task = "task"
    result = "result"
    review = "review"
    flag = "flag"
    escalate = "escalate"
    log = "log"
    heartbeat = "heartbeat"


class SupervisorState(StrEnum):
    """Orchestration states for the supervisor state machine."""

    idle = "idle"
    planning = "planning"
    executing = "executing"
    reviewing = "reviewing"
    completed = "completed"
    failed = "failed"


class TaskStatus(StrEnum):
    """Status of a research task in the plan."""

    pending = "pending"
    ready = "ready"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class ConflictStatus(StrEnum):
    """Status of a detected conflict between specialist agents."""

    open = "open"
    evidence_requested = "evidence_requested"
    escalated_to_human = "escalated_to_human"
    resolved = "resolved"
    registered_as_open_question = "registered_as_open_question"


class HandoffTrigger(StrEnum):
    """Reasons for pausing for human input."""

    ethical_tier_1 = "ethical_tier_1"
    ethical_tier_2 = "ethical_tier_2"
    resource_constraint = "resource_constraint"
    unresolved_conflict = "unresolved_conflict"
    knowledge_boundary = "knowledge_boundary"
    user_requested = "user_requested"


class HandoffStatus(StrEnum):
    """Status of a human handoff request."""

    pending = "pending"
    resolved = "resolved"
    timed_out = "timed_out"


class AgentMessage(BaseModel):
    """A typed message exchanged between agents via the AgentBus.

    The payload is a generic dict — senders and receivers agree on schema
    out of band. Typed payload helpers (QueryPayload, ResponsePayload, etc.)
    are provided for convenience and can be converted via .model_dump().
    """

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    recipient: str
    message_type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # noqa: UP017
    thread_id: str | None = None
    provenance_parent_id: str | None = None


class AgentThread(BaseModel):
    """Groups messages belonging to a single research context."""

    thread_id: str
    research_context_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # noqa: UP017
    message_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Typed payload helpers
# ---------------------------------------------------------------------------


class QueryPayload(BaseModel):
    """Payload for a query message."""

    question: str
    context: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int | None = None


class ResponsePayload(BaseModel):
    """Payload for a response message."""

    content: str
    confidence: float | None = None
    citations: list[str] = Field(default_factory=list)


class TaskPayload(BaseModel):
    """Payload for a task assignment message."""

    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    deadline: str | None = None


class ResultPayload(BaseModel):
    """Payload for a task result message."""

    task_description: str
    output: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None


class ReviewPayload(BaseModel):
    """Payload for a review/approval message."""

    target_message_id: str
    verdict: str
    comments: str = ""


class FlagPayload(BaseModel):
    """Payload for flagging an issue."""

    reason: str
    severity: str = "warning"
    target_message_id: str | None = None


class EscalatePayload(BaseModel):
    """Payload for escalating a problem to a higher authority."""

    issue: str
    target_agent: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class LogPayload(BaseModel):
    """Payload for a log/notification message."""

    level: str = "info"
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class HeartbeatPayload(BaseModel):
    """Payload for a heartbeat message from an agent."""

    agent_id: str
    status: str = "alive"
    load: float | None = None
    last_task_id: str | None = None


class HeartbeatRecord(BaseModel):
    """Tracks heartbeat state for a single agent."""

    agent_id: str
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(UTC))
    failure_count: int = 0
    consecutive_timeouts: int = 0


class ResearchTask(BaseModel):
    """A subtask in a research plan assigned to a specialist agent."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_role: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0)
    status: TaskStatus = TaskStatus.pending
    result: dict[str, Any] | None = None
    error: str | None = None
    assigned_message_id: str | None = None


class ResearchPlan(BaseModel):
    """A decomposed research question into ordered subtasks."""

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_question: str
    tasks: list[ResearchTask] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentPosition(BaseModel):
    """One agent's stance in a conflict."""

    agent_id: str
    claim: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float | None = None


class ConflictRecord(BaseModel):
    """A detected disagreement between specialist agents."""

    conflict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    positions: list[AgentPosition] = Field(default_factory=list)
    status: ConflictStatus = ConflictStatus.open
    resolution: str | None = None
    escalated_to_human: bool = False


class HandoffRequest(BaseModel):
    """A request to pause for human input."""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reason: str
    trigger: HandoffTrigger
    context: dict[str, Any] = Field(default_factory=dict)
    status: HandoffStatus = HandoffStatus.pending
    response: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    timeout_seconds: float | None = 86400.0


class SessionState(BaseModel):
    """Serialisable snapshot of an active research session."""

    session_id: str
    research_context: dict[str, Any] = Field(default_factory=dict)
    supervisor_state: SupervisorState = SupervisorState.idle
    plan: ResearchPlan | None = None
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    handoffs: list[HandoffRequest] = Field(default_factory=list)
    heartbeat_records: dict[str, HeartbeatRecord] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
