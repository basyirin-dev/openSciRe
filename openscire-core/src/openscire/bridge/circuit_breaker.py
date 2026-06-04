# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, max_failures: int = 5, reset_timeout: float = 60.0) -> None:
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_available(self) -> bool:
        if self._state == CircuitState.OPEN:
            return time.monotonic() - self._last_failure_time >= self.reset_timeout
        return True

    async def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.reset_timeout:
                    self._state = CircuitState.HALF_OPEN
                else:
                    msg = "Circuit breaker is OPEN"
                    raise CircuitBreakerOpenError(msg)

        try:
            result = await fn(*args, **kwargs)
            self.success()
            return result
        except Exception:
            self.failure()
            raise

    def success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.max_failures:
            self._state = CircuitState.OPEN


class CircuitBreakerOpenError(Exception):
    pass
