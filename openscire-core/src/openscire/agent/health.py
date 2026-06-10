# SPDX-License-Identifier: Apache-2.0

"""AgentHealthMonitor — tracks agent heartbeats, detects timeouts, manages restarts.

Agents publish HeartbeatPayload messages to the bus. The monitor subscribes
to MessageType.heartbeat and updates its records. When an agent misses its
heartbeat window (default 120s), it is flagged for restart. After max_failures
(3), the supervisor is notified via the agent_failed callback.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from openscire.agent.exceptions import AgentHealthTimeoutError
from openscire.agent.models import HeartbeatRecord


class AgentHealthMonitor:
    """Tracks agent liveness via heartbeat messages.

    Args:
        heartbeat_timeout: Seconds without a heartbeat before agent is
            considered stalled.
        max_failures: Consecutive timeouts before agent is declared dead.
        agent_failed_callback: Optional async callable invoked when an
            agent exceeds max_failures. Receives (agent_id, record).
    """

    def __init__(
        self,
        heartbeat_timeout: float = 120.0,
        max_failures: int = 3,
        agent_failed_callback: Any | None = None,  # noqa: ANN401
    ) -> None:
        self._heartbeat_timeout = heartbeat_timeout
        self._max_failures = max_failures
        self._agent_failed_callback = agent_failed_callback
        self._records: dict[str, HeartbeatRecord] = {}

    def record_heartbeat(self, agent_id: str) -> HeartbeatRecord:
        """Record a heartbeat from an agent.

        Args:
            agent_id: The agent reporting in.

        Returns:
            The updated HeartbeatRecord.
        """
        record = self._records.get(agent_id)
        if record is None:
            record = HeartbeatRecord(agent_id=agent_id)
            self._records[agent_id] = record
        record.last_heartbeat = datetime.now(UTC)
        record.failure_count = 0
        record.consecutive_timeouts = 0
        return record

    def check_timeouts(self) -> list[str]:
        """Return list of agent IDs that have timed out.

        Increments consecutive_timeouts for each timed-out agent.
        Callers should use check_timeouts_async to trigger the failure
        callback for agents that have reached max_failures.

        Returns:
            List of agent_ids that are currently timed out.
        """
        now = datetime.now(UTC)
        deadline = now - timedelta(seconds=self._heartbeat_timeout)
        timed_out: list[str] = []

        for agent_id, record in list(self._records.items()):
            if record.last_heartbeat < deadline:
                record.consecutive_timeouts += 1
                record.failure_count += 1
                timed_out.append(agent_id)

        return timed_out

    def is_healthy(self, agent_id: str) -> bool:
        """Check whether an agent is considered healthy.

        An agent is healthy if it has a recent heartbeat and has not
        exceeded the failure threshold.
        """
        record = self._records.get(agent_id)
        if record is None:
            return False
        if record.failure_count >= self._max_failures:
            return False
        now = datetime.now(UTC)
        deadline = now - timedelta(seconds=self._heartbeat_timeout)
        return record.last_heartbeat >= deadline

    def restart_agent(self, agent_id: str) -> bool:
        """Reset failure state for an agent (simulates restart).

        Args:
            agent_id: The agent to restart.

        Returns:
            True if the agent was tracked and reset, False if unknown.
        """
        record = self._records.get(agent_id)
        if record is None:
            return False
        record.failure_count = 0
        record.consecutive_timeouts = 0
        record.last_heartbeat = datetime.now(UTC)
        return True

    def get_record(self, agent_id: str) -> HeartbeatRecord | None:
        """Get the heartbeat record for an agent."""
        return self._records.get(agent_id)

    def list_agents(self) -> list[str]:
        """Return all tracked agent IDs."""
        return list(self._records.keys())

    @property
    def failed_agents(self) -> list[str]:
        return [
            aid for aid, rec in self._records.items() if rec.failure_count >= self._max_failures
        ]

    async def check_timeouts_async(self) -> list[str]:
        """Async version of check_timeouts that triggers the callback inline."""
        timed_out = self.check_timeouts()
        if self._agent_failed_callback:
            for agent_id in timed_out:
                record = self._records.get(agent_id)
                if record and record.failure_count >= self._max_failures:
                    await self._agent_failed_callback(agent_id, record)
        return timed_out

    async def _notify_failed(self, agent_id: str, record: HeartbeatRecord) -> None:
        """Invoke the failure callback if set."""
        if self._agent_failed_callback is not None and callable(self._agent_failed_callback):
            result = self._agent_failed_callback(agent_id, record)
            if hasattr(result, "__await__"):
                await result

    def raise_if_unhealthy(self, agent_id: str) -> None:
        """Raise AgentHealthTimeoutError if agent is unhealthy."""
        if not self.is_healthy(agent_id):
            record = self._records.get(agent_id)
            count = record.failure_count if record else 0
            raise AgentHealthTimeoutError(
                message=f"Agent {agent_id} unhealthy after {count} failures",
                source="AgentHealthMonitor.raise_if_unhealthy",
            )
