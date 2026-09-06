"""Video forensics — detect deepfake / AI-generated video. Asynchronous: submit, then poll."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .. import _specs
from .._poll import poll_until, poll_until_async
from .._specs import PagedResult, normalize_paged
from ..files import FileInput
from ..models import TERMINAL_JOB_STATUSES, VideoForensicsCreditInfo, VideoJob, VideoSubmitResponse

if TYPE_CHECKING:
    from ..aio import AsyncRaidClient
    from ..client import RaidClient


def _page(raw: object) -> PagedResult[VideoJob]:
    items, total = normalize_paged(raw)
    return PagedResult[VideoJob](
        items=[VideoJob.model_validate(i) for i in items], total_count=total
    )


def _is_done(job: VideoJob) -> bool:
    return job.status in TERMINAL_JOB_STATUSES


class Video:
    def __init__(self, client: RaidClient) -> None:
        self._client = client

    def submit(
        self,
        file: FileInput,
        *,
        client_duration_seconds: float | None = None,
        source_url: str | None = None,
    ) -> VideoSubmitResponse:
        """Submit a video file. Returns a ``job_id`` to poll. Requires the ``video`` scope."""
        spec = _specs.video_submit(file, client_duration_seconds, source_url)
        return self._client.request(spec, VideoSubmitResponse)

    def submit_from_url(
        self, url: str, *, client_duration_seconds: float | None = None
    ) -> VideoSubmitResponse:
        """Submit a video from a public URL. Returns a ``job_id`` to poll."""
        spec = _specs.video_submit_from_url(url, client_duration_seconds)
        return self._client.request(spec, VideoSubmitResponse)

    def get_job(self, job_id: str) -> VideoJob:
        """Fetch a video job. ``result`` is populated once ``status`` is ``Completed``."""
        return self._client.request(_specs.video_get_job(job_id), VideoJob)

    def list_jobs(
        self, *, skip: int | None = None, take: int | None = None
    ) -> PagedResult[VideoJob]:
        """List submitted video jobs, most recent first."""
        return _page(self._client.request(_specs.video_list_jobs(skip, take)))

    def cancel(self, job_id: str) -> None:
        """Cancel a running video job."""
        self._client.request(_specs.video_cancel(job_id))

    def submit_and_wait(
        self,
        file: FileInput,
        *,
        client_duration_seconds: float | None = None,
        source_url: str | None = None,
        interval_seconds: float = 3.0,
        timeout_seconds: float = 300.0,
        on_poll: Callable[[VideoJob], None] | None = None,
    ) -> VideoJob:
        """Submit a video and poll until it reaches a terminal state."""
        submitted = self.submit(
            file, client_duration_seconds=client_duration_seconds, source_url=source_url
        )
        return poll_until(
            lambda: self.get_job(submitted.job_id),
            _is_done,
            lambda j: j.status.value,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

    def credit_info(self) -> VideoForensicsCreditInfo:
        """Read the credit balance and the live video limits: cost per frame, frames analyzed per
        second, the longest video allowed and what it costs, max file size, allowed formats, and
        today's usage against the daily cap.

        Read these rather than hard-coding the defaults — they are account settings and can
        change without an SDK release. Any valid API token may call this; no scope is required.
        """
        return self._client.request(_specs.video_credit_info(), VideoForensicsCreditInfo)


class AsyncVideo:
    def __init__(self, client: AsyncRaidClient) -> None:
        self._client = client

    async def submit(
        self,
        file: FileInput,
        *,
        client_duration_seconds: float | None = None,
        source_url: str | None = None,
    ) -> VideoSubmitResponse:
        spec = _specs.video_submit(file, client_duration_seconds, source_url)
        return await self._client.request(spec, VideoSubmitResponse)

    async def submit_from_url(
        self, url: str, *, client_duration_seconds: float | None = None
    ) -> VideoSubmitResponse:
        spec = _specs.video_submit_from_url(url, client_duration_seconds)
        return await self._client.request(spec, VideoSubmitResponse)

    async def get_job(self, job_id: str) -> VideoJob:
        return await self._client.request(_specs.video_get_job(job_id), VideoJob)

    async def list_jobs(
        self, *, skip: int | None = None, take: int | None = None
    ) -> PagedResult[VideoJob]:
        return _page(await self._client.request(_specs.video_list_jobs(skip, take)))

    async def cancel(self, job_id: str) -> None:
        await self._client.request(_specs.video_cancel(job_id))

    async def submit_and_wait(
        self,
        file: FileInput,
        *,
        client_duration_seconds: float | None = None,
        source_url: str | None = None,
        interval_seconds: float = 3.0,
        timeout_seconds: float = 300.0,
        on_poll: Callable[[VideoJob], None] | None = None,
    ) -> VideoJob:
        submitted = await self.submit(
            file, client_duration_seconds=client_duration_seconds, source_url=source_url
        )
        return await poll_until_async(
            lambda: self.get_job(submitted.job_id),
            _is_done,
            lambda j: j.status.value,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

    async def credit_info(self) -> VideoForensicsCreditInfo:
        return await self._client.request(_specs.video_credit_info(), VideoForensicsCreditInfo)
