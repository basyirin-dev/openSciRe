# SPDX-License-Identifier: Apache-2.0

"""Tests for the Agent Communication Protocol (Task 6.1).

Covers AgentMessage, MessageType, AgentBus pub/sub, thread management,
provenance persistence, and async delivery.
"""

import uuid
from datetime import datetime

import pytest
from openscire.agent import (
    AgentBus,
    AgentMessage,
    EscalatePayload,
    FlagPayload,
    LogPayload,
    MessageType,
    QueryPayload,
    ResponsePayload,
    ResultPayload,
    ReviewPayload,
    TaskPayload,
)


@pytest.fixture
def reset_bus() -> None:
    AgentBus.reset()
    yield
    AgentBus.reset()


# ---------------------------------------------------------------------------
# 6.1.1 AgentMessage — typed Pydantic model
# ---------------------------------------------------------------------------


class TestAgentMessage:
    def test_defaults(self) -> None:
        msg = AgentMessage(sender="a", recipient="b", message_type=MessageType.query)
        assert uuid.UUID(msg.message_id)
        assert msg.sender == "a"
        assert msg.recipient == "b"
        assert msg.message_type == MessageType.query
        assert msg.payload == {}
        assert isinstance(msg.timestamp, datetime)
        assert msg.thread_id is None
        assert msg.provenance_parent_id is None

    def test_explicit_fields(self) -> None:
        msg = AgentMessage(
            sender="agent_01",
            recipient="agent_02",
            message_type=MessageType.task,
            payload={"key": "value"},
            thread_id="thread_abc",
            provenance_parent_id="prov_123",
        )
        assert msg.sender == "agent_01"
        assert msg.recipient == "agent_02"
        assert msg.message_type == MessageType.task
        assert msg.payload == {"key": "value"}
        assert msg.thread_id == "thread_abc"
        assert msg.provenance_parent_id == "prov_123"

    def test_serialization_roundtrip(self) -> None:
        original = AgentMessage(
            sender="a",
            recipient="b",
            message_type=MessageType.result,
            payload={"status": "ok"},
        )
        data = original.model_dump(mode="python")
        restored = AgentMessage.model_validate(data)
        assert restored.message_id == original.message_id
        assert restored.sender == original.sender
        assert restored.payload == original.payload


# ---------------------------------------------------------------------------
# 6.1.2 Message types — all 8 variants
# ---------------------------------------------------------------------------


class TestMessageType:
    def test_all_values_present(self) -> None:
        expected = {
            "query",
            "response",
            "task",
            "result",
            "review",
            "flag",
            "escalate",
            "log",
            "heartbeat",
        }
        assert set(MessageType) == expected

    def test_all_types_accepted_in_messages(self) -> None:
        for mt in MessageType:
            msg = AgentMessage(sender="a", recipient="b", message_type=mt)
            assert msg.message_type == mt


# ---------------------------------------------------------------------------
# 6.1.3 AgentBus — message routing, subscription, delivery guarantees
# ---------------------------------------------------------------------------


class TestAgentBusPubSub:
    @pytest.mark.asyncio
    async def test_direct_subscribe_and_publish(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()
        received: list[AgentMessage] = []

        async def handler(msg: AgentMessage) -> None:  # noqa: ARG001
            received.append(msg)

        bus.subscribe("agent_a", {MessageType.query}, handler)
        msg = AgentMessage(
            sender="agent_b",
            recipient="agent_a",
            message_type=MessageType.query,
        )
        bus.publish(msg)

        await _drain()
        assert len(received) == 1
        assert received[0].message_id == msg.message_id

    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_all(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()
        received_a: list[AgentMessage] = []
        received_b: list[AgentMessage] = []

        async def handler_a(msg: AgentMessage) -> None:  # noqa: ARG001
            received_a.append(msg)

        async def handler_b(msg: AgentMessage) -> None:  # noqa: ARG001
            received_b.append(msg)

        bus.subscribe("agent_a", {MessageType.query}, handler_a)
        bus.subscribe("agent_b", {MessageType.query}, handler_b)

        msg = AgentMessage(
            sender="agent_c",
            recipient="*",
            message_type=MessageType.query,
        )
        bus.publish(msg)

        await _drain()
        assert len(received_a) == 1
        assert len(received_b) == 1

    @pytest.mark.asyncio
    async def test_message_type_filtering(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()
        received: list[AgentMessage] = []

        async def handler(msg: AgentMessage) -> None:  # noqa: ARG001
            received.append(msg)

        bus.subscribe("agent_a", {MessageType.query}, handler)
        msg = AgentMessage(
            sender="agent_b",
            recipient="agent_a",
            message_type=MessageType.task,
        )
        bus.publish(msg)

        await _drain()
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_subscribe_all_types(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()
        received: list[AgentMessage] = []

        async def handler(msg: AgentMessage) -> None:  # noqa: ARG001
            received.append(msg)

        bus.subscribe("agent_a", None, handler)
        for mt in [MessageType.query, MessageType.task, MessageType.log]:
            bus.publish(AgentMessage(sender="b", recipient="agent_a", message_type=mt))

        await _drain()
        assert len(received) == 3

    @pytest.mark.asyncio
    async def test_unsubscribe(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()
        received: list[AgentMessage] = []

        async def handler(msg: AgentMessage) -> None:  # noqa: ARG001
            received.append(msg)

        sub = bus.subscribe("agent_a", None, handler)
        bus.unsubscribe(sub)

        bus.publish(
            AgentMessage(sender="b", recipient="agent_a", message_type=MessageType.query),
        )

        await _drain()
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_failed_delivery_tracking(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()

        async def failing_handler(msg: AgentMessage) -> None:  # noqa: ARG001
            raise ValueError("Handler crashed")

        bus.subscribe("agent_a", None, failing_handler)
        msg = AgentMessage(
            sender="b",
            recipient="agent_a",
            message_type=MessageType.query,
        )
        bus.publish(msg)

        await _drain()
        assert len(bus.failed_deliveries) == 1
        failed_msg, failed_recipient, err = bus.failed_deliveries[0]
        assert failed_msg.message_id == msg.message_id
        assert failed_recipient == "agent_a"
        assert err == "callback_error"


# ---------------------------------------------------------------------------
# 6.1.4 Thread management — grouping messages by research context
# ---------------------------------------------------------------------------


class TestThreadManagement:
    @pytest.mark.asyncio
    async def test_thread_auto_created(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()
        assert bus.get_thread("thread_1") is None

        msg = AgentMessage(
            sender="a",
            recipient="b",
            message_type=MessageType.query,
            thread_id="thread_1",
        )
        bus.publish(msg)

        thread = bus.get_thread("thread_1")
        assert thread is not None
        assert thread.thread_id == "thread_1"
        assert msg.message_id in thread.message_ids

    @pytest.mark.asyncio
    async def test_thread_accumulates_messages(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()

        msg1 = AgentMessage(
            sender="a",
            recipient="b",
            message_type=MessageType.query,
            thread_id="thread_2",
        )
        msg2 = AgentMessage(
            sender="b",
            recipient="a",
            message_type=MessageType.response,
            thread_id="thread_2",
        )
        bus.publish(msg1)
        bus.publish(msg2)

        thread = bus.get_thread("thread_2")
        assert thread is not None
        assert thread.message_ids == [msg1.message_id, msg2.message_id]

    @pytest.mark.asyncio
    async def test_messages_without_thread_id_not_recorded(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()

        msg = AgentMessage(
            sender="a",
            recipient="b",
            message_type=MessageType.log,
        )
        bus.publish(msg)

        assert bus.get_thread("nonexistent") is None
        assert len(bus.list_threads()) == 0


# ---------------------------------------------------------------------------
# 6.1.5 Message persistence — provenance graph storage
# ---------------------------------------------------------------------------


class MockProvenanceTracker:
    """Stand-in for ProvenanceTracker to avoid circular import at test time."""

    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []
        self._last_action_id: str | None = None

    def track(  # noqa: PLR0913
        self,
        action_type: str,
        agent_id: str = "",
        model_id: str = "",
        params: dict[str, object] | None = None,
        input_hash: str = "",
        output_hash: str = "",
        parent_ids: list[str] | None = None,
    ) -> object:
        import uuid
        from datetime import datetime

        action_id = str(uuid.uuid4())
        if parent_ids is None and self._last_action_id is not None:
            parent_ids = [self._last_action_id]

        entry: dict[str, object] = {
            "action_id": action_id,
            "action_type": action_type,
            "parent_ids": parent_ids or [],
            "agent_id": agent_id,
            "model_id": model_id,
            "parameters_snapshot": params or {},
            "input_hash": input_hash,
            "output_hash": output_hash,
            "timestamp": datetime.now(),
        }
        self.entries.append(entry)
        self._last_action_id = action_id
        return entry


class TestProvenancePersistence:
    @pytest.mark.asyncio
    async def test_message_persisted_via_tracker(self) -> None:
        tracker = MockProvenanceTracker()
        bus = AgentBus.get_bus(bus_id="provenance_test_1", provenance_tracker=tracker)  # type: ignore[arg-type]

        async def handler(msg: AgentMessage) -> None:  # noqa: ARG001
            pass

        bus.subscribe("agent_a", None, handler)
        bus.publish(
            AgentMessage(
                sender="agent_b",
                recipient="agent_a",
                message_type=MessageType.query,
            ),
        )

        await _drain()
        assert len(tracker.entries) == 1
        entry = tracker.entries[0]
        assert "agent_message.query" in str(entry["action_type"])
        assert entry["agent_id"] == "agent_b"

    @pytest.mark.asyncio
    async def test_provenance_parent_linking(self) -> None:
        tracker = MockProvenanceTracker()
        bus = AgentBus.get_bus(bus_id="provenance_test_2", provenance_tracker=tracker)  # type: ignore[arg-type]

        async def handler(msg: AgentMessage) -> None:  # noqa: ARG001
            pass

        bus.subscribe("agent_a", None, handler)

        parent = AgentMessage(
            sender="agent_b",
            recipient="agent_a",
            message_type=MessageType.query,
        )
        bus.publish(parent)
        await _drain()

        child = AgentMessage(
            sender="agent_a",
            recipient="agent_b",
            message_type=MessageType.response,
            provenance_parent_id=parent.message_id,
        )
        bus.publish(child)
        await _drain()

        # child entry should be the second entry
        assert len(tracker.entries) == 2
        child_entry = tracker.entries[1]
        assert parent.message_id in (child_entry["parent_ids"] or [])


# ---------------------------------------------------------------------------
# 6.1.6 Async message handling — non-blocking delivery
# ---------------------------------------------------------------------------


class TestAsyncDelivery:
    @pytest.mark.asyncio
    async def test_publish_does_not_block_on_slow_callback(self, reset_bus: None) -> None:  # noqa: ARG002
        bus = AgentBus.get_bus()
        slow_received: list[AgentMessage] = []
        fast_received: list[AgentMessage] = []

        async def slow_handler(msg: AgentMessage) -> None:  # noqa: ARG001
            import asyncio

            await asyncio.sleep(0.3)
            slow_received.append(msg)

        async def fast_handler(msg: AgentMessage) -> None:  # noqa: ARG001
            fast_received.append(msg)

        bus.subscribe("slow_agent", None, slow_handler)
        bus.subscribe("fast_agent", None, fast_handler)

        msg = AgentMessage(
            sender="sender",
            recipient="*",
            message_type=MessageType.log,
        )
        bus.publish(msg)

        await _drain(0.02)
        # fast handler should have executed (not blocked by slow)
        assert len(fast_received) == 1
        # slow handler is still sleeping
        assert len(slow_received) == 0

        await _drain(0.4)
        assert len(slow_received) == 1


# ---------------------------------------------------------------------------
# Payload helper model tests
# ---------------------------------------------------------------------------


class TestPayloadHelpers:
    def test_query_payload(self) -> None:
        qp = QueryPayload(question="Test question?")
        assert qp.question == "Test question?"
        assert qp.model_dump() == {
            "question": "Test question?",
            "context": {},
            "max_tokens": None,
        }

    def test_response_payload(self) -> None:
        rp = ResponsePayload(
            content="Answer",
            confidence=0.95,
            citations=["doi:10.1234/abc"],
        )
        assert rp.content == "Answer"
        assert rp.confidence == 0.95

    def test_task_payload(self) -> None:
        tp = TaskPayload(description="Do the thing", parameters={"iterations": 10})
        assert tp.description == "Do the thing"
        assert tp.parameters == {"iterations": 10}

    def test_result_payload(self) -> None:
        rp = ResultPayload(
            task_description="Do the thing",
            output={"status": "done"},
            success=True,
        )
        assert rp.success is True
        assert rp.error is None

    def test_review_payload(self) -> None:
        rvp = ReviewPayload(
            target_message_id="msg_123",
            verdict="approved",
            comments="Looks good",
        )
        assert rvp.verdict == "approved"

    def test_flag_payload(self) -> None:
        fp = FlagPayload(reason="Unsupported claim", severity="critical")
        assert fp.severity == "critical"

    def test_escalate_payload(self) -> None:
        ep = EscalatePayload(issue="Cannot resolve", target_agent="admin")
        assert ep.target_agent == "admin"

    def test_log_payload(self) -> None:
        lp = LogPayload(level="error", message="Something broke")
        assert lp.level == "error"
        assert lp.message == "Something broke"

    def test_payload_roundtrip_via_agent_message(self) -> None:
        qp = QueryPayload(question="Test?")
        msg = AgentMessage(
            sender="a",
            recipient="b",
            message_type=MessageType.query,
            payload=qp.model_dump(),
        )
        assert msg.payload["question"] == "Test?"


# ---------------------------------------------------------------------------
# Bus singleton behavior
# ---------------------------------------------------------------------------


class TestBusSingleton:
    def test_same_bus_id_returns_same_instance(self, reset_bus: None) -> None:  # noqa: ARG002
        bus1 = AgentBus.get_bus("singleton_test")
        bus2 = AgentBus.get_bus("singleton_test")
        assert bus1 is bus2

    def test_different_bus_ids_return_different_instances(self, reset_bus: None) -> None:  # noqa: ARG002
        bus1 = AgentBus.get_bus("bus_a")
        bus2 = AgentBus.get_bus("bus_b")
        assert bus1 is not bus2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _drain(sleep_s: float = 0.01) -> None:
    """Yield to the event loop to allow async callbacks to fire."""
    import asyncio

    await asyncio.sleep(sleep_s)
