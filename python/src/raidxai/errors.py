"""Exceptions raised by the Raid AI SDK."""

from __future__ import annotations

from typing import Any


class RaidApiError(Exception):
    """A non-2xx response from the Raid AI API.

    The API returns a ``{"error": {"code", "message"}}`` envelope, but middleware,
    controller catch-blocks, and proxies can each emit a slightly different shape
    (``{"message"}``, ``{"error": "…"}``, or a raw string). ``message`` is unwrapped
    from whichever shape came back; ``code`` is the stable machine-readable code
    when present (e.g. ``IMAGE_FORENSICS:FILE_TOO_LARGE``, ``api_key.scope_missing``).
    """

    def __init__(
        self,
        status: int,
        message: str,
        *,
        code: str | None = None,
        body: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code
        self.body = body
        self.request_id = request_id

    @property
    def is_auth(self) -> bool:
        """True for 401/403 — token missing, invalid, or lacking the endpoint's scope."""
        return self.status in (401, 403)

    @property
    def is_payment_required(self) -> bool:
        """True for 402 — a credit/quota/paywall limit (e.g. ``USER_CREDIT_LIMIT_REACHED``)."""
        return self.status == 402

    @property
    def is_rate_limited(self) -> bool:
        """True for 429 — rate limited."""
        return self.status == 429

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"RaidApiError(status={self.status}, code={self.code!r}, message={self.message!r})"


class RaidTimeoutError(Exception):
    """Raised when a ``submit_and_wait`` poll loop exceeds its timeout."""

    def __init__(self, message: str, last_status: str | None = None) -> None:
        super().__init__(message)
        self.last_status = last_status


def extract_error(body: Any) -> tuple[str | None, str | None]:
    """Pull ``(message, code)`` out of any backend error body.

    Handles every error shape the API can return: ``{"error": {"code", "message"}}``,
    ``{"message"}``, ``{"error": "str"}``, ``{"code"}``, and a raw string body.
    """
    if isinstance(body, str):
        return (body or None, None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            code = err.get("code")
            message = err.get("message")
            return (
                message if isinstance(message, str) else None,
                code if isinstance(code, str) else None,
            )
        if isinstance(err, str):
            code = body.get("code")
            return (err, code if isinstance(code, str) else None)
        message = body.get("message")
        if isinstance(message, str):
            code = body.get("code")
            return (message, code if isinstance(code, str) else None)
        code = body.get("code")
        if isinstance(code, str):
            return (None, code)
    return (None, None)
