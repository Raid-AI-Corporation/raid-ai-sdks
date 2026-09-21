"""Synchronous Raid AI client."""

from __future__ import annotations

import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from ._core import (
    RequestSpec,
    backoff_seconds,
    build_headers,
    is_retryable_status,
    parse_response,
    retry_delay,
)
from .errors import RaidApiError
from .resources.audio import Audio
from .resources.documents import Documents
from .resources.fact_checking import FactChecking
from .resources.images import Images
from .resources.video import Video

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_BASE_URL = "https://api.raidxai.com"

TModel = TypeVar("TModel", bound=BaseModel)


class RaidClient:
    """Synchronous client for the Raid AI detection API.

    ::

        from raidxai import RaidClient, FileInput

        raid = RaidClient(api_key="<your-api-key>")
        res = raid.images.process(FileInput.from_path("photo.jpg"))
        print(res.images[0].verdict)

    Use as a context manager (``with RaidClient(...) as raid:``) to close the
    underlying connection pool, or call :meth:`close`.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        auth_header: str = "bearer",
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("RaidClient: api_key is required (your developer token).")
        self._max_retries = max_retries
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=(base_url or DEFAULT_BASE_URL).rstrip("/"),
            headers=build_headers(api_key, auth_header),
            timeout=timeout,
            transport=transport,
        )

        self.images = Images(self)
        self.audio = Audio(self)
        self.video = Video(self)
        self.documents = Documents(self)
        self.fact_checking = FactChecking(self)

    # ── request core ──────────────────────────────────────────────────────────
    def request(self, spec: RequestSpec, model: type[TModel] | None = None) -> Any:
        """Execute ``spec`` with retries; parse into ``model`` when given.

        Retries 429 / ≥500 / transport errors with exponential backoff; fails fast
        on other 4xx.
        """
        attempts = self._max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = self._http.request(spec.method, spec.path, **spec.httpx_kwargs())
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < attempts:
                    time.sleep(backoff_seconds(attempt))
                    continue
                raise RaidApiError(0, f"Request to {spec.path} failed: {exc}", body=exc) from exc

            if is_retryable_status(response.status_code) and attempt < attempts:
                time.sleep(retry_delay(response, attempt))
                continue

            parsed = parse_response(response, spec.path, binary=spec.binary)
            return model.model_validate(parsed) if model is not None else parsed

        raise RaidApiError(
            0, f"Request to {spec.path} failed after {attempts} attempts", body=last_exc
        )

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> RaidClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
