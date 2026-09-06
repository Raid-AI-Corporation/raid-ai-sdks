"""Image forensics — detect AI-generated, deepfaked, and digitally edited images. Synchronous."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .. import _specs
from .._poll import poll_until, poll_until_async
from ..files import FileInput
from ..models import (
    ImageBatch,
    ImageBatchCancelResult,
    ImageBatchPage,
    ImageBatchResultPage,
    ImageBatchSubmitResponse,
    ImageForensicsCreditInfo,
    ImageForensicsResponse,
)

if TYPE_CHECKING:
    from ..aio import AsyncRaidClient
    from ..client import RaidClient


def _to_list(files: FileInput | list[FileInput]) -> list[FileInput]:
    return files if isinstance(files, list) else [files]


class Images:
    def __init__(self, client: RaidClient) -> None:
        self._client = client

    def process(
        self,
        files: FileInput | list[FileInput],
        *,
        external_id: str | None = None,
        source_url: str | None = None,
    ) -> ImageForensicsResponse:
        """Analyze one or more image files (up to 10). Requires the ``image`` scope."""
        spec = _specs.image_process(_to_list(files), external_id, source_url)
        return self._client.request(spec, ImageForensicsResponse)

    def process_from_url(
        self, url: str, *, external_id: str | None = None
    ) -> ImageForensicsResponse:
        """Analyze an image fetched from a public URL."""
        spec = _specs.image_process_from_url(url, external_id)
        return self._client.request(spec, ImageForensicsResponse)

    def submit_batch(
        self,
        files: list[FileInput],
        *,
        external_id: str | None = None,
    ) -> ImageBatchSubmitResponse:
        """Queue images for analysis in a later scheduled window, at a reduced credit cost.

        Returns immediately with a batch id -- **no verdicts**. Credits are deducted on
        acceptance and refunded for any image that ultimately fails.

        Batch mode is images-only; no other modality has a batch tier.

        Two differences from :meth:`process` are structural, not temporary:

        * **Turnaround is up to a full processing window**, so never put this on a path where a
          person is waiting.
        * **Results are basic tier** -- ``deep_analysis``, ``generators`` and ``heatmap_url`` are
          always ``None``, whatever the plan. Those are realtime-only.
        """
        spec = _specs.image_submit_batch(files, external_id=external_id)
        return self._client.request(spec, ImageBatchSubmitResponse)

    def get_batch(self, batch_id: str) -> ImageBatch:
        """Current status and counters for one batch."""
        return self._client.request(_specs.image_get_batch(batch_id), ImageBatch)

    def list_batches(self, *, skip: int | None = None, take: int | None = None) -> ImageBatchPage:
        """Your batches, newest first."""
        return self._client.request(_specs.image_list_batches(skip=skip, take=take), ImageBatchPage)

    def batch_results(
        self, batch_id: str, *, skip: int | None = None, take: int | None = None
    ) -> ImageBatchResultPage:
        """Per-image results.

        Individual images become available as they finish -- you do not have to wait for the whole
        batch. Match results to your inputs with ``ordinal``, the image's position in the original
        submission; file names are echoed back but are not guaranteed unique.
        """
        spec = _specs.image_batch_results(batch_id, skip=skip, take=take)
        return self._client.request(spec, ImageBatchResultPage)

    def cancel_batch(self, batch_id: str) -> ImageBatchCancelResult:
        """Cancel the images still waiting and refund their credits.

        Images already being analyzed are left to finish -- they have consumed the work either
        way -- so the refund covers only what was actually cancelled.
        """
        return self._client.request(_specs.image_cancel_batch(batch_id), ImageBatchCancelResult)

    def submit_batch_and_wait(
        self,
        files: list[FileInput],
        *,
        external_id: str | None = None,
        interval_seconds: float = 3.0,
        timeout_seconds: float = 300.0,
        on_poll: Callable[[ImageBatch], None] | None = None,
    ) -> ImageBatch:
        """Queue a batch and poll until it is terminal, then return it.

        **Rarely what you want.** A batch can legitimately take hours, so this holds the process
        open for the whole window and the default timeout will usually expire first. Prefer
        :meth:`submit_batch`, persist the id, and collect results later -- that is the point of
        the tier. This exists for tests and short-window setups.

        Polling stops on the server-computed ``is_terminal`` rather than a status allow-list, so
        it keeps working if a status is ever added.
        """
        submitted = self.submit_batch(files, external_id=external_id)
        batch_id = submitted.batch_id
        if batch_id is None:
            raise ValueError("submit_batch did not return a batch_id")

        return poll_until(
            lambda: self.get_batch(str(batch_id)),
            lambda b: b.is_terminal is True,
            lambda b: b.status.value if b.status else "unknown",
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

    def credit_info(self) -> ImageForensicsCreditInfo:
        """Read the credit balance and the live image limits: cost per image, max file size and
        allowed formats, plus whether the batch tier is available and what it costs.

        Read these rather than hard-coding the defaults — they are account settings and can
        change without an SDK release. Any valid API token may call this; no scope is required.
        """
        return self._client.request(_specs.image_credit_info(), ImageForensicsCreditInfo)


class AsyncImages:
    def __init__(self, client: AsyncRaidClient) -> None:
        self._client = client

    async def process(
        self,
        files: FileInput | list[FileInput],
        *,
        external_id: str | None = None,
        source_url: str | None = None,
    ) -> ImageForensicsResponse:
        spec = _specs.image_process(_to_list(files), external_id, source_url)
        return await self._client.request(spec, ImageForensicsResponse)

    async def process_from_url(
        self, url: str, *, external_id: str | None = None
    ) -> ImageForensicsResponse:
        spec = _specs.image_process_from_url(url, external_id)
        return await self._client.request(spec, ImageForensicsResponse)


    async def submit_batch(
        self,
        files: list[FileInput],
        *,
        external_id: str | None = None,
    ) -> ImageBatchSubmitResponse:
        """Queue images for analysis in a later scheduled window, at a reduced credit cost.

        Returns immediately with a batch id -- **no verdicts**. Credits are deducted on
        acceptance and refunded for any image that ultimately fails.

        Batch mode is images-only; no other modality has a batch tier.

        Two differences from :meth:`process` are structural, not temporary:

        * **Turnaround is up to a full processing window**, so never put this on a path where a
          person is waiting.
        * **Results are basic tier** -- ``deep_analysis``, ``generators`` and ``heatmap_url`` are
          always ``None``, whatever the plan. Those are realtime-only.
        """
        spec = _specs.image_submit_batch(files, external_id=external_id)
        return await self._client.request(spec, ImageBatchSubmitResponse)

    async def get_batch(self, batch_id: str) -> ImageBatch:
        """Current status and counters for one batch."""
        return await self._client.request(_specs.image_get_batch(batch_id), ImageBatch)

    async def list_batches(
        self, *, skip: int | None = None, take: int | None = None
    ) -> ImageBatchPage:
        """Your batches, newest first."""
        spec = _specs.image_list_batches(skip=skip, take=take)
        return await self._client.request(spec, ImageBatchPage)

    async def batch_results(
        self, batch_id: str, *, skip: int | None = None, take: int | None = None
    ) -> ImageBatchResultPage:
        """Per-image results.

        Individual images become available as they finish -- you do not have to wait for the whole
        batch. Match results to your inputs with ``ordinal``, the image's position in the original
        submission; file names are echoed back but are not guaranteed unique.
        """
        spec = _specs.image_batch_results(batch_id, skip=skip, take=take)
        return await self._client.request(spec, ImageBatchResultPage)

    async def cancel_batch(self, batch_id: str) -> ImageBatchCancelResult:
        """Cancel the images still waiting and refund their credits.

        Images already being analyzed are left to finish -- they have consumed the work either
        way -- so the refund covers only what was actually cancelled.
        """
        spec = _specs.image_cancel_batch(batch_id)
        return await self._client.request(spec, ImageBatchCancelResult)

    async def submit_batch_and_wait(
        self,
        files: list[FileInput],
        *,
        external_id: str | None = None,
        interval_seconds: float = 3.0,
        timeout_seconds: float = 300.0,
        on_poll: Callable[[ImageBatch], None] | None = None,
    ) -> ImageBatch:
        """Queue a batch and poll until it is terminal, then return it.

        **Rarely what you want.** A batch can legitimately take hours, so this holds the process
        open for the whole window and the default timeout will usually expire first. Prefer
        :meth:`submit_batch`, persist the id, and collect results later -- that is the point of
        the tier. This exists for tests and short-window setups.

        Polling stops on the server-computed ``is_terminal`` rather than a status allow-list, so
        it keeps working if a status is ever added.
        """
        submitted = await self.submit_batch(files, external_id=external_id)
        batch_id = submitted.batch_id
        if batch_id is None:
            raise ValueError("submit_batch did not return a batch_id")

        return await poll_until_async(
            lambda: self.get_batch(str(batch_id)),
            lambda b: b.is_terminal is True,
            lambda b: b.status.value if b.status else "unknown",
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

    async def credit_info(self) -> ImageForensicsCreditInfo:
        return await self._client.request(_specs.image_credit_info(), ImageForensicsCreditInfo)
