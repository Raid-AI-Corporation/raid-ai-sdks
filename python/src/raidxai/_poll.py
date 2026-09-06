"""Sync and async poll loops for the ``submit_and_wait`` helpers."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .errors import RaidTimeoutError

T = TypeVar("T")

DEFAULT_INTERVAL_SECONDS = 3.0
DEFAULT_TIMEOUT_SECONDS = 300.0


def poll_until(
    fetch_once: Callable[[], T],
    is_done: Callable[[T], bool],
    describe_status: Callable[[T], str],
    *,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    on_poll: Callable[[T], None] | None = None,
) -> T:
    deadline = time.monotonic() + timeout_seconds
    last: T | None = None
    while True:
        last = fetch_once()
        if on_poll is not None:
            on_poll(last)
        if is_done(last):
            return last
        # Give up only once the deadline has actually passed, so the full budget is
        # used; clamp the sleep so we never overshoot the deadline waiting to poll.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RaidTimeoutError(
                f"Timed out after {timeout_seconds}s waiting for the job to finish",
                describe_status(last),
            )
        time.sleep(min(interval_seconds, remaining))


async def poll_until_async(
    fetch_once: Callable[[], Awaitable[T]],
    is_done: Callable[[T], bool],
    describe_status: Callable[[T], str],
    *,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    on_poll: Callable[[T], None] | None = None,
) -> T:
    deadline = time.monotonic() + timeout_seconds
    last: T | None = None
    while True:
        last = await fetch_once()
        if on_poll is not None:
            on_poll(last)
        if is_done(last):
            return last
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RaidTimeoutError(
                f"Timed out after {timeout_seconds}s waiting for the job to finish",
                describe_status(last),
            )
        await asyncio.sleep(min(interval_seconds, remaining))
