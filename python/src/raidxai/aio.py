"""Asynchronous Raid AI client."""

from __future__ import annotations

import asyncio
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
from .client import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT_SECONDS
from .errors import RaidApiError
from .resources.audio import AsyncAudio
from .resources.documents import AsyncDocuments
from .resources.fact_checking import AsyncFactChecking
from .resources.images import AsyncImages
from .resources.video import AsyncVideo

TModel = TypeVar("TModel", bound=BaseModel)


class AsyncRaidClient:
    """Asynchronous client for the Raid AI detection API.

    ::

        from raidxai import AsyncRaidClient, FileInput

        async with AsyncRaidClient(api_key="<your-api-key>", base_url="<raid-ai-api-url>") as raid:
            res = await raid.images.process(FileInput.from_path("photo.jpg"))
            print(res.images[0].verdict)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        auth_header: str = "bearer",
        http_client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "AsyncRaidClient: api_key is required (your developer token)."
            )
        if not base_url:
            raise ValueError(
                "AsyncRaidClient: base_url is required (the Raid AI API base URL)."
            )
        self._max_retries = max_retries
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=build_headers(api_key, auth_header),
            timeout=timeout,
            transport=transport,
        )

        self.images = AsyncImages(self)
        self.audio = AsyncAudio(self)
        self.video = AsyncVideo(self)
        self.documents = AsyncDocuments(self)
        self.fact_checking = AsyncFactChecking(self)

    async def request(self, spec: RequestSpec, model: type[TModel] | None = None) -> Any:
        """Execute ``spec`` with retries; parse into ``model`` when given."""
        attempts = self._max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self._http.request(spec.method, spec.path, **spec.httpx_kwargs())
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < attempts:
                    await asyncio.sleep(backoff_seconds(attempt))
                    continue
                raise RaidApiError(0, f"Request to {spec.path} failed: {exc}", body=exc) from exc

            if is_retryable_status(response.status_code) and attempt < attempts:
                await asyncio.sleep(retry_delay(response, attempt))
                continue

            parsed = parse_response(response, spec.path, binary=spec.binary)
            return model.model_validate(parsed) if model is not None else parsed

        raise RaidApiError(
            0, f"Request to {spec.path} failed after {attempts} attempts", body=last_exc
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncRaidClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
