"""Basic in-memory rate limiting for the auth endpoints. The app runs as a
single process today (audit §4.1 notes it had no limiting at all and relied on
Telegram as the throttle), so a per-process sliding window keyed by client IP +
path is sufficient for phase 2a. If the API ever scales to multiple replicas
this needs a shared backend.
"""

import time
from collections import deque

from fastapi import HTTPException, Request

from app.config import get_settings

_WINDOW_SECONDS = 60.0


class _RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def check(self, key: tuple[str, str], limit: int) -> bool:
        now = time.monotonic()
        window = self._hits.setdefault(key, deque())
        cutoff = now - _WINDOW_SECONDS
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True


limiter = _RateLimiter()


async def auth_rate_limit(request: Request) -> None:
    client = request.client.host if request.client is not None else "unknown"
    if not limiter.check((request.url.path, client), get_settings().mobile_auth_rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="too many requests")


async def message_rate_limit(request: Request) -> None:
    client = request.client.host if request.client is not None else "unknown"
    if not limiter.check((request.url.path, client), get_settings().mobile_message_rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="too many requests")
