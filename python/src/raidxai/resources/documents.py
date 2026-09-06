"""Document analysis — one upload returns both a document-level forensics verdict and
per-page tampering / AI-generation results. Asynchronous: analyze, then poll."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .. import _specs
from .._core import BinaryResponse
from .._poll import poll_until, poll_until_async
from ..files import FileInput
from ..models import (
    TERMINAL_DOCUMENT_STATUSES,
    DocumentAnalysis,
    DocumentAnalysisCreditInfo,
    DocumentType,
)

if TYPE_CHECKING:
    from ..aio import AsyncRaidClient
    from ..client import RaidClient

#: A full analysis runs for minutes, so the poll budget is far longer than the other
#: modalities' 5 minutes. Raise it with ``timeout_seconds`` for long documents.
DEFAULT_ANALYZE_TIMEOUT_SECONDS = 900.0


def _is_done(analysis: DocumentAnalysis) -> bool:
    """True once an analysis will not change again."""
    return analysis.status in TERMINAL_DOCUMENT_STATUSES


def _doc_type(doc_type: DocumentType | str | None) -> str | None:
    return doc_type.value if isinstance(doc_type, DocumentType) else doc_type


class Documents:
    def __init__(self, client: RaidClient) -> None:
        self._client = client

    def analyze(
        self, file: FileInput, *, doc_type: DocumentType | str | None = None
    ) -> DocumentAnalysis:
        """Upload a PDF or image for analysis. Requires the ``document-image`` scope.

        Returns the analysis record whether the server finished inside its wait budget or
        not — the shape is identical either way, so check ``status`` (usually
        ``processing``) and poll :meth:`get` with ``id``. Never re-upload to "retry" a
        still-running analysis: the record already exists, and a second upload is a second
        charge.
        """
        spec = _specs.document_analyze(file, _doc_type(doc_type))
        return self._client.request(spec, DocumentAnalysis)

    def get(self, analysis_id: str) -> DocumentAnalysis:
        """Fetch one analysis. ``pages`` grows and ``verdict`` fills in as it progresses."""
        return self._client.request(_specs.document_get(analysis_id), DocumentAnalysis)

    def analyze_and_wait(
        self,
        file: FileInput,
        *,
        doc_type: DocumentType | str | None = None,
        interval_seconds: float = 3.0,
        timeout_seconds: float = DEFAULT_ANALYZE_TIMEOUT_SECONDS,
        on_poll: Callable[[DocumentAnalysis], None] | None = None,
    ) -> DocumentAnalysis:
        """Upload a document and poll until it is ``completed`` or ``failed``."""
        submitted = self.analyze(file, doc_type=doc_type)
        # The upload may already have come back terminal — don't spend a poll to learn that.
        if _is_done(submitted):
            if on_poll is not None:
                on_poll(submitted)
            return submitted
        return poll_until(
            lambda: self.get(str(submitted.id)),
            _is_done,
            lambda a: a.status.value,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

    def page_image(self, analysis_id: str, page_number: int) -> BinaryResponse:
        """Fetch the rendered raster for one page (``image/png``).

        These are the exact pixels a page's ``edited_regions`` coordinates are measured
        against, so region boxes can be drawn on it directly. Available while the page's
        ``has_image`` is true.
        """
        return self._client.request(_specs.document_page_image(analysis_id, page_number))

    def evidence(
        self,
        analysis_id: str,
        *,
        feature: str,
        page: int | None = None,
        redaction: str | None = None,
    ) -> BinaryResponse:
        """Fetch one forensics evidence raster for a feature lane and page.

        ``feature`` is ``tampering``, ``consistency`` or ``anomaly``. The storage URI is
        resolved server-side from this analysis's own verdict — a crop is addressed by lane
        and page, never by URI.
        """
        return self._client.request(
            _specs.document_evidence(analysis_id, feature, page, redaction)
        )

    def credit_info(self) -> DocumentAnalysisCreditInfo:
        """Read the live credit balance and upload constraints.

        Call it before a batch instead of hard-coding the defaults — the size ceilings,
        batch limit and concurrency are server-side settings and can change without an
        SDK release.
        """
        return self._client.request(_specs.document_credit_info(), DocumentAnalysisCreditInfo)


class AsyncDocuments:
    def __init__(self, client: AsyncRaidClient) -> None:
        self._client = client

    async def analyze(
        self, file: FileInput, *, doc_type: DocumentType | str | None = None
    ) -> DocumentAnalysis:
        spec = _specs.document_analyze(file, _doc_type(doc_type))
        return await self._client.request(spec, DocumentAnalysis)

    async def get(self, analysis_id: str) -> DocumentAnalysis:
        return await self._client.request(_specs.document_get(analysis_id), DocumentAnalysis)

    async def analyze_and_wait(
        self,
        file: FileInput,
        *,
        doc_type: DocumentType | str | None = None,
        interval_seconds: float = 3.0,
        timeout_seconds: float = DEFAULT_ANALYZE_TIMEOUT_SECONDS,
        on_poll: Callable[[DocumentAnalysis], None] | None = None,
    ) -> DocumentAnalysis:
        submitted = await self.analyze(file, doc_type=doc_type)
        if _is_done(submitted):
            if on_poll is not None:
                on_poll(submitted)
            return submitted
        return await poll_until_async(
            lambda: self.get(str(submitted.id)),
            _is_done,
            lambda a: a.status.value,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            on_poll=on_poll,
        )

    async def page_image(self, analysis_id: str, page_number: int) -> BinaryResponse:
        return await self._client.request(_specs.document_page_image(analysis_id, page_number))

    async def evidence(
        self,
        analysis_id: str,
        *,
        feature: str,
        page: int | None = None,
        redaction: str | None = None,
    ) -> BinaryResponse:
        return await self._client.request(
            _specs.document_evidence(analysis_id, feature, page, redaction)
        )

    async def credit_info(self) -> DocumentAnalysisCreditInfo:
        return await self._client.request(
            _specs.document_credit_info(), DocumentAnalysisCreditInfo
        )
