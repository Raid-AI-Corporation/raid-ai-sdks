"""Voice analysis — detect AI-generated / cloned voices, plus optional transcription.

``detection_confidence`` on the response is confidence in the verdict that was reported,
measured as distance past the decision boundary — NOT the probability that the audio is
AI-generated. ``0.5`` means the clip landed on the boundary itself, and the opposite verdict's
confidence is not ``1 - detection_confidence``.

``metadata`` is typed as :class:`~raidxai.models.VoiceDetectionDetails` for the detection
workflow. Which detector runs is chosen per account by the Raid AI platform — there is no
selector on the request — and every field is optional. The number to show a user is
``metadata.score`` (a percentile against the detector's own genuine speech, valid when
``score_basis`` says so); ``metadata.p_fake`` is a raw ranking, not a probability, and must not
be shown as a percentage. ``metadata.provider`` names the detector that produced the verdict, as
an open string. Keys the spec leaves untyped are kept on ``metadata.model_extra``.

The response's ``workflow_type`` is the workflow's *name* (``"AiDetectionOnly"``) even though the
request takes the number from :class:`VoiceWorkflow`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import _specs
from ..files import FileInput
from ..models import VoiceAnalysisCreditInfo, VoiceAnalysisResponse

if TYPE_CHECKING:
    from ..aio import AsyncRaidClient
    from ..client import RaidClient


class VoiceWorkflow:
    """Voice workflow selector (mirrors the API's ``input.WorkflowType``)."""

    TRANSCRIPTION_ONLY = 1
    INTELLIGENCE_ONLY = 2
    COMBINED = 3
    AI_DETECTION_ONLY = 4  # default


class Audio:
    def __init__(self, client: RaidClient) -> None:
        self._client = client

    def process(
        self,
        file: FileInput,
        *,
        workflow_type: int | None = None,
        text_input: str | None = None,
        context_hints: str | None = None,
        source_url: str | None = None,
    ) -> VoiceAnalysisResponse:
        """Analyze an audio file. Requires the ``audio`` scope."""
        spec = _specs.audio_process(file, workflow_type, text_input, context_hints, source_url)
        return self._client.request(spec, VoiceAnalysisResponse)

    def process_from_url(
        self,
        url: str,
        *,
        workflow_type: int | None = None,
        text_input: str | None = None,
        context_hints: str | None = None,
    ) -> VoiceAnalysisResponse:
        """Analyze audio fetched from a public URL."""
        spec = _specs.audio_process_from_url(url, workflow_type, text_input, context_hints)
        return self._client.request(spec, VoiceAnalysisResponse)

    def credit_info(self) -> VoiceAnalysisCreditInfo:
        """Read the credit balance and the live audio limits: what each workflow costs, which ones
        the balance currently covers, max file size, allowed formats and the batch limit.

        Read these rather than hard-coding the defaults — they are account settings and can
        change without an SDK release. Any valid API token may call this; no scope is required.
        """
        return self._client.request(_specs.audio_credit_info(), VoiceAnalysisCreditInfo)


class AsyncAudio:
    def __init__(self, client: AsyncRaidClient) -> None:
        self._client = client

    async def process(
        self,
        file: FileInput,
        *,
        workflow_type: int | None = None,
        text_input: str | None = None,
        context_hints: str | None = None,
        source_url: str | None = None,
    ) -> VoiceAnalysisResponse:
        spec = _specs.audio_process(file, workflow_type, text_input, context_hints, source_url)
        return await self._client.request(spec, VoiceAnalysisResponse)

    async def process_from_url(
        self,
        url: str,
        *,
        workflow_type: int | None = None,
        text_input: str | None = None,
        context_hints: str | None = None,
    ) -> VoiceAnalysisResponse:
        spec = _specs.audio_process_from_url(url, workflow_type, text_input, context_hints)
        return await self._client.request(spec, VoiceAnalysisResponse)

    async def credit_info(self) -> VoiceAnalysisCreditInfo:
        return await self._client.request(_specs.audio_credit_info(), VoiceAnalysisCreditInfo)
