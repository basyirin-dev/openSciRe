# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    def __init__(self, rate: float, burst: int = 1) -> None:
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(float(self.burst), self._tokens + elapsed * self.rate)
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

            wait = (1.0 - self._tokens) / self.rate if self.rate > 0 else 0.1
            await asyncio.sleep(wait)

    def on_429(self) -> None:
        self.rate *= 0.5
        if self.rate < 0.01:
            self.rate = 0.01
