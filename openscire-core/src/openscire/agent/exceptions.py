# SPDX-License-Identifier: Apache-2.0

"""Agent-specific exceptions for bus routing and message validation."""

from openscire.constants import ErrorCode
from openscire.exceptions import openSciReError


class AgentBusError(openSciReError):
    """Raised on agent bus routing and delivery failures."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.AGENT_BUS_ROUTING,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class AgentMessageError(openSciReError):
    """Raised when an invalid message is encountered."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.AGENT_INVALID_MESSAGE,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class SupervisorError(openSciReError):
    """Raised on supervisor agent orchestration failures."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.AGENT_SUPERVISOR,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class AgentHealthTimeoutError(openSciReError):
    """Raised when an agent heartbeat times out."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.AGENT_HEALTH_TIMEOUT,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class ConflictUnresolvedError(openSciReError):
    """Raised when a conflict cannot be resolved automatically."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.AGENT_CONFLICT_UNRESOLVED,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)


class HandoffPendingError(openSciReError):
    """Raised when a human handoff is pending resolution."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
        error_code: ErrorCode = ErrorCode.AGENT_HANDOFF_PENDING,
    ) -> None:
        super().__init__(error_code=error_code, message=message, source=source)
