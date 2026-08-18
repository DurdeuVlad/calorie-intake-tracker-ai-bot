"""Ported from MessagingExecutionContext.java. Marks "we are already inside the
live message-handling flow" so DailyStatusService.refresh() can skip a
synchronous pinned-status refresh triggered from within it (avoids redundant
work; the provider-neutral MessagingDailyStatusService.refresh() handles the
per-turn update instead). contextvars.ContextVar is the asyncio-safe
equivalent of Java's ThreadLocal here -- it's correctly isolated per task."""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import TypeVar

_ACTIVE: ContextVar[bool] = ContextVar("messaging_execution_active", default=False)

T = TypeVar("T")


async def run(work: Callable[[], Awaitable[T]]) -> T:
    token = _ACTIVE.set(True)
    try:
        return await work()
    finally:
        _ACTIVE.reset(token)


def active() -> bool:
    return _ACTIVE.get()
