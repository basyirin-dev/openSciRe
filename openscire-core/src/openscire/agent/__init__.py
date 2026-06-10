# SPDX-License-Identifier: Apache-2.0

"""Agent communication protocol and supervisor orchestration.

Provides AgentBus (pub/sub messaging), typed message models, SupervisorAgent
(orchestrator with state machine, task queue, health monitoring, conflict
resolution, human handoff, and session persistence).
"""

from openscire.agent.bus import AgentBus, Subscription
from openscire.agent.conflict import ConflictResolver
from openscire.agent.diversity import DiversityAssignmentError, DiversityManager
from openscire.agent.ethics_agent import EthicsAgent
from openscire.agent.exceptions import (
    AgentBusError,
    AgentHealthTimeoutError,
    AgentMessageError,
    ConflictUnresolvedError,
    HandoffPendingError,
    SupervisorError,
)
from openscire.agent.falsification import FalsificationAgent
from openscire.agent.handoff import HumanHandoff
from openscire.agent.health import AgentHealthMonitor
from openscire.agent.literature_review import LiteratureReviewAgent
from openscire.agent.models import (
    AgentMessage,
    AgentPosition,
    AgentThread,
    ConflictRecord,
    ConflictStatus,
    EscalatePayload,
    FlagPayload,
    HandoffRequest,
    HandoffStatus,
    HandoffTrigger,
    HeartbeatPayload,
    HeartbeatRecord,
    LogPayload,
    MessageType,
    QueryPayload,
    ResearchPlan,
    ResearchTask,
    ResponsePayload,
    ResultPayload,
    ReviewPayload,
    SessionState,
    SupervisorState,
    TaskPayload,
    TaskStatus,
)
from openscire.agent.session import SessionManager
from openscire.agent.state import SupervisorStateMachine
from openscire.agent.supervisor import SupervisorAgent
from openscire.agent.workflow import (
    WorkflowBuilder,
    WorkflowDefinition,
    WorkflowOrchestrator,
    WorkflowProgress,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
    WorkflowTemplate,
)

__all__ = [
    "AgentBus",
    "AgentMessage",
    "AgentThread",
    "AgentBusError",
    "AgentHealthTimeoutError",
    "AgentHealthMonitor",
    "AgentMessageError",
    "AgentPosition",
    "ConflictRecord",
    "ConflictResolver",
    "ConflictStatus",
    "ConflictUnresolvedError",
    "DiversityAssignmentError",
    "DiversityManager",
    "EscalatePayload",
    "EthicsAgent",
    "FalsificationAgent",
    "FlagPayload",
    "HandoffPendingError",
    "HandoffRequest",
    "HandoffStatus",
    "HandoffTrigger",
    "HeartbeatPayload",
    "HeartbeatRecord",
    "HumanHandoff",
    "LiteratureReviewAgent",
    "LogPayload",
    "MessageType",
    "QueryPayload",
    "ResearchPlan",
    "ResearchTask",
    "ResponsePayload",
    "ResultPayload",
    "ReviewPayload",
    "SessionManager",
    "SessionState",
    "Subscription",
    "SupervisorAgent",
    "SupervisorError",
    "SupervisorState",
    "SupervisorStateMachine",
    "TaskPayload",
    "TaskStatus",
    "WorkflowBuilder",
    "WorkflowDefinition",
    "WorkflowOrchestrator",
    "WorkflowProgress",
    "WorkflowStatus",
    "WorkflowStep",
    "WorkflowStepStatus",
    "WorkflowTemplate",
]
