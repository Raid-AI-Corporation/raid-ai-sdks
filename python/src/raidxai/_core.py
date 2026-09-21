"""Transport-agnostic request plumbing shared by the sync and async clients.

A :class:`RequestSpec` is a pure description of one HTTP call (built by the
functions in ``_specs.py``). The sync and async clients each know how to execute
a spec with retries; everything else — header/URL building, response parsing,
error mapping, backoff math — lives here so both paths behave identically.
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .errors import RaidApiError, extract_error

# A multipart file part: (field_name, (filename, data, content_type)).
FilePart = tuple[str, tuple[str, bytes, str]]


@dataclass(frozen=True)
class BinaryResponse:
    """A raw-bytes response — the document page rasters and evidence crops."""

    data: bytes
    #: The response's ``Content-Type``, e.g. ``image/png``.
    content_type: str


@dataclass
class RequestSpec:
    method: str
    path: str
    json: Any = None
    data: dict[str, str] = field(default_factory=dict)
    files: list[FilePart] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    #: Expect raw bytes rather than JSON — resolves to a :class:`BinaryResponse`.
    binary: bool = False

    def httpx_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.binary:
            # A binary endpoint still answers errors as JSON, so accept both rather than
            # narrowing to one image type.
            kwargs["headers"] = {"Accept": "*/*"}
        if self.files:
            kwargs["files"] = self.files
            if self.data:
                kwargs["data"] = self.data
        elif self.json is not None:
            kwargs["json"] = self.json
        if self.params:
            kwargs["params"] = {k: v for k, v in self.params.items() if v is not None}
        return kwargs


def build_headers(api_key: str, auth_header: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if auth_header == "x-api-key":
        headers["X-Api-Key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def is_retryable_status(status: int) -> bool:
    return status == 429 or status >= 500


def backoff_seconds(attempt: int) -> float:
    """0.5s, 1s, 2s, … (attempt is 1-based)."""
    return 0.5 * (2 ** (attempt - 1))


def retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse a ``Retry-After`` header — either delta-seconds or an HTTP-date.

    Returns ``None`` when absent/unparseable; ``0.0`` is a valid "retry now" value
    and is preserved (callers must not treat it as falsy).
    """
    header = response.headers.get("retry-after")
    if not header:
        return None
    try:
        return max(0.0, float(header))
    except ValueError:
        pass
    # HTTP-date form, e.g. "Wed, 16 Jul 2026 12:00:05 GMT" (sent by many proxies/CDNs).
    try:
        when = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def retry_delay(response: httpx.Response, attempt: int) -> float:
    """The delay before a retry: the server's ``Retry-After`` if given, else backoff.

    Uses an explicit ``None`` check so a ``Retry-After: 0`` (retry immediately) is honored
    rather than falling through to exponential backoff.
    """
    after = retry_after_seconds(response)
    return after if after is not None else backoff_seconds(attempt)


def parse_response(response: httpx.Response, path: str, *, binary: bool = False) -> Any:
    """Return the parsed body, or raise :class:`RaidApiError` on a non-2xx.

    With ``binary`` the success path returns a :class:`BinaryResponse` and the bytes are
    never decoded as text; a failure still falls through to the JSON error mapping below,
    so error handling is identical either way.
    """
    request_id = response.headers.get("request-id") or response.headers.get("x-request-id")

    if response.status_code == 204:
        return None

    if binary and response.is_success:
        return BinaryResponse(
            data=response.content,
            content_type=response.headers.get("content-type", "application/octet-stream"),
        )

    text = response.text
    parsed: Any = text
    if "application/json" in response.headers.get("content-type", "") and text:
        try:
            parsed = _json.loads(text)
        except ValueError:
            parsed = text

    if not response.is_success:
        message, code = extract_error(parsed)
        raise RaidApiError(
            response.status_code,
            message or f"API error {response.status_code}: {response.reason_phrase}",
            code=code,
            body=parsed,
            request_id=request_id,
        )

    return parsed
