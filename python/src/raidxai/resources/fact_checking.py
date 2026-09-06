"""Fact-checking — check media against the public record. Asynchronous: submit, then poll."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .. import _specs
from .._poll import poll_until, poll_until_async
from .._specs import PagedResult, normalize_paged
from ..files import FileInput
from ..models import (
    TERMINAL_JOB_STATUSES,
    FactCheckingCreditInfo,
    FactCheckJob,
    JobSubmitResponse,
    Modality,
)

if TYPE_CHECKING:
    from ..aio import AsyncRaidClient
    from ..client import RaidClient

ModalityArg = Modality | str


def _modality_str(modality: ModalityArg) -> str:
    return modality.value if isinstance(modality, Modality) else modality


def _page(raw: object) -> PagedResult[FactCheckJob]:
    items, total = normalize_paged(raw)
    return PagedResult[FactCheckJob](
        items=[FactCheckJob.model_validate(i) for i in items], total_count=total
    )


def _is_done(job: FactCheckJob) -> bool:
    return job.status in TERMINAL_JOB_STATUSES


class FactChecking:
    def __init__(self, client: RaidClient) -> None:
        self._client = client

    def submit(
        self, file: FileInput, modality: ModalityArg, *, user_context: str | None = None
    ) -> JobSubmitResponse:
        """Submit media to fact-check. Returns a ``job_id`` to poll. Needs the fact-check scope."""
        spec = _specs.factcheck_submit(file, _modality_str(modality), user_context)
        return self._client.request(spec, JobSubmitResponse)

    def submit_from_url(
        self, url: str, modality: ModalityArg, *, user_context: str | None = None
    ) -> JobSubmitResponse:
        """Submit media from a public URL to fact-check."""
        spec = _specs.factcheck_submit_from_url(url, _modality_str(modality), user_context)
        return self._client.request(spec, JobSubmitResponse)

    def get_job(self, job_id: str) -> FactCheckJob:
        """Fetch a fact-checking job. ``result`` is populated once ``status`` is ``Completed``."""
        return self._client.request(_specs.factcheck_get_job(job_id), FactCheckJob)

    def list_jobs(
        self, *, skip: int | None = None, take: int | None = None
    ) -> PagedResult[FactCheckJob]:
        """List submitted fact-checking jobs, most recent first."""
        return _page(self._client.request(_specs.factcheck_list_jobs(skip, take)))

    def cancel(self, job_id: str) -> None:
        """Cancel a running fact-checking job."""
        self._client.request(_specs.factcheck_cancel(job_id))

    def submit_and_wait(
        self,
        file: FileInput,
        modality: ModalityArg,
        *,
        user_context: str | None = None,
        interval_seconds: float = 3.0,
        timeout_seconds: float = 300.0,
        on_poll: Callable[[FactCheckJob], None] | None = None,
    ) -> FactCheckJob:
        """Submit a fact-check and poll until it reaches a terminal state."""
        submitted = self.submit(file, modality, user_context=user_context)
        return poll_until(
            lambda: self.get_job(submitted.job_id),
            _is_done,
            lambda j: j.status.value,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

    def credit_info(self) -> FactCheckingCreditInfo:
        """Read the credit balance and the live fact-checking limits: the cost per modality, the
        per-job credit cap, max file size and allowed formats.

        Read these rather than hard-coding the defaults — they are account settings and can
        change without an SDK release. Any valid API token may call this; no scope is required.
        """
        return self._client.request(_specs.factcheck_credit_info(), FactCheckingCreditInfo)


class AsyncFactChecking:
    def __init__(self, client: AsyncRaidClient) -> None:
        self._client = client

    async def submit(
        self, file: FileInput, modality: ModalityArg, *, user_context: str | None = None
    ) -> JobSubmitResponse:
        spec = _specs.factcheck_submit(file, _modality_str(modality), user_context)
        return await self._client.request(spec, JobSubmitResponse)

    async def submit_from_url(
        self, url: str, modality: ModalityArg, *, user_context: str | None = None
    ) -> JobSubmitResponse:
        spec = _specs.factcheck_submit_from_url(url, _modality_str(modality), user_context)
        return await self._client.request(spec, JobSubmitResponse)

    async def get_job(self, job_id: str) -> FactCheckJob:
        return await self._client.request(_specs.factcheck_get_job(job_id), FactCheckJob)

    async def list_jobs(
        self, *, skip: int | None = None, take: int | None = None
    ) -> PagedResult[FactCheckJob]:
        return _page(await self._client.request(_specs.factcheck_list_jobs(skip, take)))

    async def cancel(self, job_id: str) -> None:
        await self._client.request(_specs.factcheck_cancel(job_id))

    async def submit_and_wait(
        self,
        file: FileInput,
        modality: ModalityArg,
        *,
        user_context: str | None = None,
        interval_seconds: float = 3.0,
        timeout_seconds: float = 300.0,
        on_poll: Callable[[FactCheckJob], None] | None = None,
    ) -> FactCheckJob:
        submitted = await self.submit(file, modality, user_context=user_context)
        return await poll_until_async(
            lambda: self.get_job(submitted.job_id),
            _is_done,
            lambda j: j.status.value,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

    async def credit_info(self) -> FactCheckingCreditInfo:
        return await self._client.request(_specs.factcheck_credit_info(), FactCheckingCreditInfo)
