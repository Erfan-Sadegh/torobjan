import asyncio
import time

import pytest

from app.services.torob_rate_limiter import TorobRateLimiter


@pytest.mark.asyncio
async def test_torob_rate_limiter_serializes_requests() -> None:
    limiter = TorobRateLimiter(0.05)
    started: list[float] = []

    async def worker() -> None:
        await limiter.acquire()
        started.append(time.monotonic())

    await asyncio.gather(worker(), worker(), worker())

    assert len(started) == 3
    assert started[1] - started[0] >= 0.04
    assert started[2] - started[1] >= 0.04
