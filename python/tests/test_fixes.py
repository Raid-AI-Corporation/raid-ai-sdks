"""Regression tests for the review-driven fixes."""

from __future__ import annotations

import time

import httpx
import pytest

from conftest import make_response, sync_client
from raidxai import FileInput, RaidTimeoutError

JOB = "9a8b7c6d-1234-5678-90ab-cdef12345678"


def _video_job(status: str) -> dict:
    return {
        "id": JOB,
        "fileName": "c.mp4",
        "status": status,
        "progress": 100,
        "creditsReserved": 1,
        "creditsUsed": 1,
        "processingTimeMs": 1,
        "createdAt": "2026-01-01T00:00:00Z",
    }


def test_retry_after_zero_retries_immediately():
    # Retry-After: 0 must not fall through to exponential backoff.
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return make_response(200, [])  # empty video.list_jobs() page

    start = time.monotonic()
    sync_client(handler, max_retries=2).video.list_jobs()
    elapsed = time.monotonic() - start
    assert calls["n"] == 2
    assert elapsed < 0.4  # would be ~0.5s if the 0 were treated as falsy


def test_retry_after_http_date_is_parsed():
    from raidxai._core import retry_after_seconds

    past = httpx.Response(429, headers={"retry-after": "Wed, 01 Jan 2020 00:00:00 GMT"})
    # A past date → 0 seconds (clamped), not None (which would mean "unparseable").
    assert retry_after_seconds(past) == 0.0


def test_from_url_omits_none_fields():
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        import json

        seen["body"] = json.loads(req.content)
        return make_response(
            200,
            {
                "isSuccessful": True,
                "workflowType": "AiDetectionOnly",
                "processingTimeMs": 1,
                "creditsUsed": 1,
            },
        )

    sync_client(handler).audio.process_from_url("https://x/y.mp3")
    # Only url is sent; optional fields are omitted, not sent as null.
    assert seen["body"] == {"url": "https://x/y.mp3"}


def test_poll_uses_full_timeout_budget():
    # A job that completes on the poll that lands right at the deadline must be caught,
    # not falsely timed out one interval early.
    statuses = iter(["Processing", "Processing", "Completed"])

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return make_response(200, {"jobId": JOB, "creditsReserved": 1})
        return make_response(200, _video_job(next(statuses, "Completed")))

    # Old off-by-one threw before the 3rd poll; the fixed loop uses the full budget.
    job = sync_client(handler).video.submit_and_wait(
        FileInput(data=b"\x00", file_name="c.mp4", content_type="video/mp4"),
        interval_seconds=0.05,
        timeout_seconds=0.12,
    )
    assert job.status.value == "Completed"


def test_on_poll_callback_invoked():
    seen: list[str] = []
    statuses = iter(["Processing", "Completed"])

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return make_response(200, {"jobId": JOB, "creditsReserved": 1})
        return make_response(200, _video_job(next(statuses, "Completed")))

    sync_client(handler).video.submit_and_wait(
        FileInput(data=b"\x00", file_name="c.mp4", content_type="video/mp4"),
        interval_seconds=0.001,
        timeout_seconds=5,
        on_poll=lambda j: seen.append(j.status.value),
    )
    assert seen == ["Processing", "Completed"]


def test_poll_times_out_when_never_done():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return make_response(200, {"jobId": JOB, "creditsReserved": 1})
        return make_response(200, _video_job("Processing"))

    with pytest.raises(RaidTimeoutError):
        sync_client(handler).video.submit_and_wait(
            FileInput(data=b"\x00", file_name="c.mp4", content_type="video/mp4"),
            interval_seconds=0.005,
            timeout_seconds=0.02,
        )
