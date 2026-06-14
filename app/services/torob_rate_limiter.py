from __future__ import annotations

import asyncio
import time

from app.settings import settings


class TorobRateLimiter:
    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = max(0.0, interval_seconds)
        self._lock = asyncio.Lock()
        self._next_allowed_at = 0.0

    async def acquire(self) -> None:
        if self.interval_seconds <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self._next_allowed_at - now)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._next_allowed_at = time.monotonic() + self.interval_seconds


_limiter: TorobRateLimiter | None = None


def get_torob_rate_limiter() -> TorobRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = TorobRateLimiter(settings.torob_rate_limit_seconds)
    return _limiter
