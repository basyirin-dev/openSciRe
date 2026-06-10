# SPDX-License-Identifier: Apache-2.0

"""AgentBus — pub/sub message bus with async delivery, thread management,
and optional provenance persistence.

Usage:
    bus = AgentBus.get_bus(provenance_tracker=tracker)

    async def my_handler(msg: AgentMessage) -> None:
        print(f"Got: {msg.payload}")

    bus.subscribe("agent_a", {MessageType.query}, my_handler)
    bus.publish(AgentMessage(sender="agent_b", recipient="agent_a",
                             message_type=MessageType.query))
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from openscire.agent.models import AgentMessage, AgentThread, MessageType

if TYPE_CHECKING:
    from openscire.provenance.tracker import ProvenanceTracker


def _log() -> object:
    """Lazily-initialised logger to avoid circular imports during startup."""
    import logging

    return logging.getLogger("openscire.agent.bus")


class Subscription:
    """A registered subscription linking an agent to message types.

    Attributes:
        agent_id: Subscribing agent identifier.
        message_types: Set of MessageTypes to receive, or None for all.
        callback: Async callable invoked on each matching message.
        active: Whether the subscription is still active.
    """

    def __init__(
        self,
        agent_id: str,
        message_types: set[MessageType] | None,
        callback: Callable[[AgentMessage], Awaitable[None]],
    ) -> None:
        self.agent_id = agent_id
        self.message_types = message_types
        self.callback = callback
        self.active = True


class AgentBus:
    """Message bus for inter-agent communication.

    Provides pub/sub routing, async delivery, thread grouping, and
    optional provenance persistence. Singleton-per-bus_id pattern
    (matching ProvenanceTracker).

    Args:
        bus_id: Unique bus identifier for singleton access.
        provenance_tracker: Optional tracker for message persistence.
    """

    _instances: dict[str, AgentBus] = {}

    def __init__(
        self,
        bus_id: str = "default",
        provenance_tracker: ProvenanceTracker | None = None,
    ) -> None:
        self._bus_id = bus_id
        self._provenance_tracker = provenance_tracker
        self._subscriptions: list[Subscription] = []
        self._threads: dict[str, AgentThread] = {}
        self._failed_deliveries: list[tuple[AgentMessage, str, str]] = []

    @classmethod
    def get_bus(
        cls,
        bus_id: str = "default",
        provenance_tracker: ProvenanceTracker | None = None,
    ) -> AgentBus:
        """Get or create a singleton AgentBus for the given bus_id.

        Args:
            bus_id: Unique identifier for the bus instance.
            provenance_tracker: Optional tracker attached on first creation.

        Returns:
            The singleton AgentBus instance.
        """
        if bus_id not in cls._instances:
            cls._instances[bus_id] = cls(
                bus_id=bus_id,
                provenance_tracker=provenance_tracker,
            )
        return cls._instances[bus_id]

    @classmethod
    def reset(cls) -> None:
        """Clear all bus instances (useful for testing)."""
        cls._instances.clear()

    def publish(self, message: AgentMessage) -> str:
        """Publish a message to the bus for asynchronous delivery.

        The message is persisted to provenance (if configured), recorded
        in its thread (if thread_id is set), and then delivered
        asynchronously to all matching subscribers.

        Args:
            message: The AgentMessage to publish.

        Returns:
            The message_id for tracking.
        """
        self._persist_message(message)
        self._record_thread(message)

        recipients = self._resolve_recipients(message)
        if not recipients:
            _log().warning(
                "No subscribers for message %s type=%s recipient=%s",
                message.message_id,
                message.message_type.value,
                message.recipient,
            )

        for recipient_id in recipients:
            asyncio.create_task(self._deliver_to(message, recipient_id))

        return message.message_id

    def subscribe(
        self,
        agent_id: str,
        message_types: set[MessageType] | None,
        callback: Callable[[AgentMessage], Awaitable[None]],
    ) -> Subscription:
        """Register a subscription for an agent.

        Args:
            agent_id: Identifier of the subscribing agent.
            message_types: Set of MessageTypes to receive, or None for all.
            callback: Async callable invoked for each matching message.

        Returns:
            A Subscription object (use to unsubscribe).
        """
        sub = Subscription(
            agent_id=agent_id,
            message_types=message_types,
            callback=callback,
        )
        self._subscriptions.append(sub)
        _log().debug(
            "Agent subscribed agent=%s types=%s",
            agent_id,
            [t.value for t in (message_types or [])],
        )
        return sub

    def unsubscribe(self, subscription: Subscription) -> None:
        """Deactivate and remove a subscription.

        Args:
            subscription: The Subscription to remove.
        """
        subscription.active = False
        self._subscriptions = [s for s in self._subscriptions if s.active]
        _log().debug("Agent unsubscribed agent=%s", subscription.agent_id)

    def get_thread(self, thread_id: str) -> AgentThread | None:
        """Retrieve a thread by its ID.

        Args:
            thread_id: The thread identifier.

        Returns:
            The AgentThread if found, None otherwise.
        """
        return self._threads.get(thread_id)

    def list_threads(self) -> list[AgentThread]:
        """Return all tracked threads.

        Returns:
            List of AgentThread instances.
        """
        return list(self._threads.values())

    @property
    def failed_deliveries(self) -> list[tuple[AgentMessage, str, str]]:
        """Return list of (message, recipient, error) for failed deliveries."""
        return list(self._failed_deliveries)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_recipients(self, message: AgentMessage) -> list[str]:
        """Resolve recipient agent IDs for a message.

        For broadcast (recipient="*"), returns all subscribers whose
        message type filters match.  For direct delivery, returns just
        the specified recipient — type matching is enforced in _deliver_to.
        """
        if message.recipient == "*":
            broadcast_recipients: set[str] = set()
            for sub in self._subscriptions:
                if not sub.active:
                    continue
                if sub.message_types is None or message.message_type in sub.message_types:
                    broadcast_recipients.add(sub.agent_id)
            return list(broadcast_recipients)

        return [message.recipient]

    async def _deliver_to(self, message: AgentMessage, recipient_id: str) -> None:
        """Deliver a message to every matching subscription for recipient_id."""
        delivery_count = 0
        for sub in self._subscriptions:
            if not sub.active:
                continue
            if sub.agent_id != recipient_id:
                continue
            if sub.message_types is not None and message.message_type not in sub.message_types:
                continue
            delivery_count += 1
            try:
                await sub.callback(message)
            except Exception:
                _log().exception(
                    "Message delivery failed msg=%s recipient=%s",
                    message.message_id,
                    recipient_id,
                )
                self._failed_deliveries.append((message, recipient_id, "callback_error"))

        if delivery_count == 0:
            _log().warning(
                "No matching subscription for delivery msg=%s recipient=%s type=%s",
                message.message_id,
                recipient_id,
                message.message_type.value,
            )

    def _persist_message(self, message: AgentMessage) -> None:
        """Record the message as a provenance entry."""
        if self._provenance_tracker is None:
            return
        try:
            parent_ids: list[str] | None = None
            if message.provenance_parent_id:
                parent_ids = [message.provenance_parent_id]

            self._provenance_tracker.track(
                action_type=f"agent_message.{message.message_type.value}",
                agent_id=message.sender,
                params=message.model_dump(mode="python"),
                parent_ids=parent_ids,
            )
        except Exception:
            _log().exception(
                "Failed to persist message to provenance msg=%s",
                message.message_id,
            )

    def _record_thread(self, message: AgentMessage) -> None:
        """Associate a message with its thread."""
        if not message.thread_id:
            return
        if message.thread_id not in self._threads:
            self._threads[message.thread_id] = AgentThread(
                thread_id=message.thread_id,
            )
        self._threads[message.thread_id].message_ids.append(message.message_id)
