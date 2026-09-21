"""Shared test helpers: build clients backed by a mocked httpx transport."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from raidxai import AsyncRaidClient, RaidClient


def json_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def make_response(
    status: int, body: object, headers: dict[str, str] | None = None
) -> httpx.Response:
    text = body if isinstance(body, str) else json.dumps(body)
    return httpx.Response(
        status,
        content=text,
        headers={"content-type": "application/json", **(headers or {})},
    )


# Neutral base URL for tests (a reserved .test TLD — not a real host).
TEST_BASE_URL = "https://api.example.test"


def sync_client(handler: Callable[[httpx.Request], httpx.Response], **kwargs) -> RaidClient:
    # Inject the mock transport (not a full client) so the SDK still builds the
    # base URL + auth headers the way it does in production.
    kwargs.setdefault("max_retries", 0)
    kwargs.setdefault("base_url", TEST_BASE_URL)
    return RaidClient(api_key="test-key", transport=json_transport(handler), **kwargs)


def async_client(
    handler: Callable[[httpx.Request], httpx.Response], **kwargs
) -> AsyncRaidClient:
    kwargs.setdefault("max_retries", 0)
    kwargs.setdefault("base_url", TEST_BASE_URL)
    return AsyncRaidClient(api_key="test-key", transport=httpx.MockTransport(handler), **kwargs)
