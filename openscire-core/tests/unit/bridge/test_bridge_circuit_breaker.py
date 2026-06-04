import asyncio

import pytest
from openscire.bridge.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_initial_state_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True

    @pytest.mark.asyncio
    async def test_failure_counting(self) -> None:
        cb = CircuitBreaker(max_failures=3)
        cb.failure()
        assert cb._failure_count == 1
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_open_at_threshold(self) -> None:
        cb = CircuitBreaker(max_failures=2)
        cb.failure()
        cb.failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False

    @pytest.mark.asyncio
    async def test_half_open_recovery(self) -> None:
        cb = CircuitBreaker(max_failures=2, reset_timeout=0.05)
        cb.failure()
        cb.failure()
        assert cb.state == CircuitState.OPEN
        await asyncio.sleep(0.06)
        assert cb.is_available is True

        async def dummy() -> str:
            return "ok"

        result = await cb.call(dummy)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_timeout(self) -> None:
        cb = CircuitBreaker(max_failures=1, reset_timeout=0.05)
        cb.failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False
        await asyncio.sleep(0.06)
        assert cb.is_available is True

    @pytest.mark.asyncio
    async def test_call_wrapper(self) -> None:
        cb = CircuitBreaker(max_failures=1)

        async def failing() -> str:
            msg = "fail"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="fail"):
            await cb.call(failing)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_default_config(self) -> None:
        cb = CircuitBreaker()
        assert cb.max_failures == 5
        assert cb.reset_timeout == 60.0
