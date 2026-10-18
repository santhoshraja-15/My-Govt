"""Small in-process sliding-window rate limiter for abuse-prone endpoints.

LIMITATION (documented): state is per process. With several workers each has its own window, so the
effective limit is limit x workers; a shared store (Redis) is needed for strict global limits.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self._clock = limit, window_seconds, clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, float]:
        """Record a hit; return (allowed, retry_after_seconds)."""
        now = self._clock()
        q = self._hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False, max(self.window - (now - q[0]), 0.0)
        q.append(now)
        return True, 0.0

    def reset(self) -> None:
        self._hits.clear()


def rate_limit(limiter: SlidingWindowLimiter, scope: str):
    """FastAPI dependency: 429 + Retry-After when the caller's IP exceeds the limiter."""
    async def _dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        ok, retry = limiter.check(f"{scope}:{ip}")
        if not ok:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again later.",
                                headers={"Retry-After": str(int(retry) + 1)})
    return _dep


# Production-sensible defaults; tests replace/reset these.
login_limiter = SlidingWindowLimiter(limit=10, window_seconds=60)
register_limiter = SlidingWindowLimiter(limit=5, window_seconds=3600)
chat_limiter = SlidingWindowLimiter(limit=30, window_seconds=60)
