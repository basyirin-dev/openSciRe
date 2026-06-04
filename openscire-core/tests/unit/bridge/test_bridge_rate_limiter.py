import asyncio

import pytest
from openscire.bridge.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_timing(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0, burst=1)
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1  # should be near-instant with fresh tokens

    @pytest.mark.asyncio
    async def test_burst_accumulation(self) -> None:
        limiter = TokenBucketRateLimiter(rate=100.0, burst=3)
        start = asyncio.get_event_loop().time()
        for _ in range(3):
            await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.2  # burst should allow all 3 near-instantly

    @pytest.mark.asyncio
    async def test_burst_exhausted_waits(self) -> None:
        limiter = TokenBucketRateLimiter(rate=100.0, burst=1)
        await limiter.acquire()  # consume burst token
        start = asyncio.get_event_loop().time()
        await limiter.acquire()  # should wait for refill
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed > 0.005  # should have waited at least a little

    @pytest.mark.asyncio
    async def test_concurrent_consumers(self) -> None:
        limiter = TokenBucketRateLimiter(rate=100.0, burst=3)

        async def acquire() -> None:
            await limiter.acquire()

        tasks = [asyncio.create_task(acquire()) for _ in range(3)]
        await asyncio.gather(*tasks)
        # All 3 should complete without error

    @pytest.mark.asyncio
    async def test_429_backoff_reduces_rate(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)
        original_rate = limiter.rate
        limiter.on_429()
        assert limiter.rate == original_rate * 0.5

    @pytest.mark.asyncio
    async def test_429_floor(self) -> None:
        limiter = TokenBucketRateLimiter(rate=0.005, burst=1)
        for _ in range(10):
            limiter.on_429()
        assert limiter.rate >= 0.01

    @pytest.mark.asyncio
    async def test_no_wait_with_no_contention(self) -> None:
        limiter = TokenBucketRateLimiter(rate=1000.0, burst=10)
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.05
