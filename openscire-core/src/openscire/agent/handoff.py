# SPDX-License-Identifier: Apache-2.0

"""HumanHandoff — detects handoff triggers and manages pause/resume for human input.

Integrates with EthicalFirewall tier governance (Tier 1 cooling-off, Tier 2
human checkpoint) and supervisor-level triggers (resource constraints,
unresolved conflicts, knowledge boundaries, user request).
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from openscire.agent.exceptions import HandoffPendingError
from openscire.agent.models import (
    HandoffRequest,
    HandoffStatus,
    HandoffTrigger,
)


class HumanHandoff:
    """Manages human-in-the-loop pauses during research sessions.

    Args:
        default_timeout: Default seconds to wait for human response (24h).
    """

    def __init__(self, default_timeout: float = 86400.0) -> None:
        self._pending: dict[str, HandoffRequest] = {}
        self._resolved: dict[str, HandoffRequest] = {}
        self._default_timeout = default_timeout
        self._events: dict[str, asyncio.Event] = {}

    def request_handoff(
        self,
        reason: str,
        trigger: HandoffTrigger,
        context: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> HandoffRequest:
        """Create a handoff request and pause execution.

        Args:
            reason: Human-readable explanation of why handoff is needed.
            trigger: The category of trigger.
            context: Additional context for the human reviewer.
            timeout: Maximum seconds to wait (default 86400 = 24h).

        Returns:
            The created HandoffRequest (status=pending).
        """
        request = HandoffRequest(
            reason=reason,
            trigger=trigger,
            context=context or {},
            timeout_seconds=timeout or self._default_timeout,
        )
        self._pending[request.request_id] = request
        self._events[request.request_id] = asyncio.Event()
        return request

    async def wait_for_resolution(self, request_id: str) -> HandoffRequest:
        """Block until the handoff is resolved or times out.

        Args:
            request_id: The handoff request to wait for.

        Returns:
            The resolved (or timed-out) HandoffRequest.

        Raises:
            HandoffPendingError: If request_id is unknown.
        """
        if request_id not in self._pending:
            request = self._resolved.get(request_id)
            if request:
                return request
            raise HandoffPendingError(
                message=f"Unknown handoff request: {request_id}",
                source="HumanHandoff.wait_for_resolution",
            )

        event = self._events.get(request_id)
        if event is None:
            event = asyncio.Event()
            self._events[request_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=self._default_timeout)
        except TimeoutError:
            self._timeout(request_id)

        return self._pending.get(request_id) or self._resolved.get(request_id)

    def resolve(self, request_id: str, response: dict[str, Any] | None = None) -> HandoffRequest:
        """Resolve a pending handoff with human input.

        Args:
            request_id: The handoff to resolve.
            response: The human's response data.

        Returns:
            The resolved HandoffRequest.
        """
        request = self._pending.pop(request_id, None)
        if request is None:
            request = self._resolved.get(request_id)
            if request:
                return request
            raise HandoffPendingError(
                message=f"Unknown handoff request: {request_id}",
                source="HumanHandoff.resolve",
            )

        request.status = HandoffStatus.resolved
        request.response = response
        request.resolved_at = datetime.now(UTC)
        self._resolved[request_id] = request

        event = self._events.pop(request_id, None)
        if event is not None:
            event.set()

        return request

    def _timeout(self, request_id: str) -> HandoffRequest:
        """Mark a handoff as timed out."""
        request = self._pending.pop(request_id, None)
        if request is None:
            return None

        request.status = HandoffStatus.timed_out
        request.resolved_at = datetime.now(UTC)
        self._resolved[request_id] = request

        event = self._events.pop(request_id, None)
        if event is not None:
            event.set()

        return request

    def has_pending(self) -> bool:
        """Check whether any handoff requests are pending."""
        return len(self._pending) > 0

    @property
    def pending_requests(self) -> list[HandoffRequest]:
        return list(self._pending.values())

    @property
    def resolved_requests(self) -> list[HandoffRequest]:
        return list(self._resolved.values())
