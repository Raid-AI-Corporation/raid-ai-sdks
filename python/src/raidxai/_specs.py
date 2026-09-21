"""Pure builders that turn method arguments into :class:`RequestSpec` objects.

Keeping the request shape in one place lets the sync and async resource classes be
thin one-liners over identical logic — the only difference between them is how the
spec is executed (``httpx.Client`` vs ``httpx.AsyncClient``).
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from urllib.parse import quote

from pydantic import BaseModel

from ._core import RequestSpec
from .files import FileInput

T = TypeVar("T")


def _json_body(**fields: Any) -> dict[str, Any]:
    """Build a JSON body, dropping ``None`` values so an omitted optional isn't sent
    as an explicit ``null`` (matches the TypeScript client, and lets the server apply
    its own default for an absent field)."""
    return {k: v for k, v in fields.items() if v is not None}


class PagedResult(BaseModel, Generic[T]):
    """A page of ``?skip=&take=`` list results."""

    items: list[T]
    total_count: int


def normalize_paged(raw: Any) -> tuple[list[Any], int]:
    """Normalize a list response (bare array or ``{items,totalCount}``) into ``(items, total)``."""
    if isinstance(raw, list):
        return raw, len(raw)
    if isinstance(raw, dict):
        items = raw.get("items")
        if not isinstance(items, list):
            items = raw.get("data") if isinstance(raw.get("data"), list) else []
        total = raw.get("totalCount")
        return items, total if isinstance(total, int) else len(items)
    return [], 0


# ── Image ─────────────────────────────────────────────────────────────────────
def _form_fields(**fields: str | None) -> dict[str, str] | None:
    """Drop unset fields so an omitted option is absent rather than sent as an empty value."""
    present = {k: v for k, v in fields.items() if v is not None}
    return present or None


def image_process(
    files: list[FileInput], external_id: str | None, source_url: str | None
) -> RequestSpec:
    if not files:
        raise ValueError("images.process: provide at least one image file.")
    data: dict[str, str] = {}
    if external_id is not None:
        data["input.ExternalId"] = external_id
    if source_url is not None:
        data["sourceUrl"] = source_url
    return RequestSpec(
        method="POST",
        path="/api/app/image-forensics/process",
        files=[f.to_part("imageFiles") for f in files],
        data=data,
    )


def image_process_from_url(url: str, external_id: str | None) -> RequestSpec:
    return RequestSpec(
        method="POST",
        path="/api/app/image-forensics/process-from-url",
        json=_json_body(url=url, externalId=external_id),
    )


# ── Audio ─────────────────────────────────────────────────────────────────────
def image_submit_batch(
    files: list[FileInput],
    *,
    external_id: str | None = None,
) -> RequestSpec:
    """Queue images for later analysis. Returns a batch id, never verdicts."""
    if not files:
        raise ValueError("submit_batch requires at least one image")

    return RequestSpec(
        method="POST",
        path="/api/app/image-forensics/batches",
        files=[f.to_part("imageFiles") for f in files],
        data=_form_fields(**{"input.ExternalId": external_id}),
    )


def image_get_batch(batch_id: str) -> RequestSpec:
    return RequestSpec(
        method="GET",
        path=f"/api/app/image-forensics/batches/{quote(batch_id, safe='')}",
    )


def image_list_batches(*, skip: int | None = None, take: int | None = None) -> RequestSpec:
    return RequestSpec(
        method="GET",
        path="/api/app/image-forensics/batches",
        params={"skip": skip, "take": take},
    )


def image_batch_results(
    batch_id: str, *, skip: int | None = None, take: int | None = None
) -> RequestSpec:
    return RequestSpec(
        method="GET",
        path=f"/api/app/image-forensics/batches/{quote(batch_id, safe='')}/results",
        params={"skip": skip, "take": take},
    )


def image_cancel_batch(batch_id: str) -> RequestSpec:
    return RequestSpec(
        method="POST",
        path=f"/api/app/image-forensics/batches/{quote(batch_id, safe='')}/cancel",
        json={},
    )


def audio_process(
    file: FileInput,
    workflow_type: int | None,
    text_input: str | None,
    context_hints: str | None,
    source_url: str | None,
) -> RequestSpec:
    data: dict[str, str] = {}
    if workflow_type is not None:
        data["input.WorkflowType"] = str(int(workflow_type))
    if text_input is not None:
        data["input.TextInput"] = text_input
    if context_hints is not None:
        data["input.ContextHints"] = context_hints
    if source_url is not None:
        data["sourceUrl"] = source_url
    return RequestSpec(
        method="POST",
        path="/api/app/voice-analysis/process",
        files=[file.to_part("audioFile")],
        data=data,
    )


def audio_process_from_url(
    url: str, workflow_type: int | None, text_input: str | None, context_hints: str | None
) -> RequestSpec:
    return RequestSpec(
        method="POST",
        path="/api/app/voice-analysis/process-from-url",
        json=_json_body(
            url=url,
            workflowType=workflow_type,
            textInput=text_input,
            contextHints=context_hints,
        ),
    )


# ── Video ─────────────────────────────────────────────────────────────────────
def video_submit(
    file: FileInput, client_duration_seconds: float | None, source_url: str | None
) -> RequestSpec:
    data: dict[str, str] = {}
    if client_duration_seconds is not None:
        data["clientDurationSeconds"] = str(client_duration_seconds)
    if source_url is not None:
        data["sourceUrl"] = source_url
    return RequestSpec(
        method="POST",
        path="/api/app/video-forensics/submit",
        files=[file.to_part("file")],
        data=data,
    )


def video_submit_from_url(url: str, client_duration_seconds: float | None) -> RequestSpec:
    return RequestSpec(
        method="POST",
        path="/api/app/video-forensics/submit-from-url",
        json=_json_body(url=url, clientDurationSeconds=client_duration_seconds),
    )


def video_get_job(job_id: str) -> RequestSpec:
    return RequestSpec(method="GET", path=f"/api/app/video-forensics/jobs/{job_id}")


def video_list_jobs(skip: int | None, take: int | None) -> RequestSpec:
    return RequestSpec(
        method="GET", path="/api/app/video-forensics/jobs", params={"skip": skip, "take": take}
    )


def video_cancel(job_id: str) -> RequestSpec:
    return RequestSpec(method="POST", path=f"/api/app/video-forensics/jobs/{job_id}/cancel")


# ── Fact-checking ──────────────────────────────────────────────────────────────
def factcheck_submit(file: FileInput, modality: str, user_context: str | None) -> RequestSpec:
    data: dict[str, str] = {"modality": modality}
    if user_context is not None:
        data["userContext"] = user_context
    return RequestSpec(
        method="POST",
        path="/api/app/fact-checking/submit",
        files=[file.to_part("file")],
        data=data,
    )


def factcheck_submit_from_url(url: str, modality: str, user_context: str | None) -> RequestSpec:
    return RequestSpec(
        method="POST",
        path="/api/app/fact-checking/submit-from-url",
        json=_json_body(url=url, modality=modality, userContext=user_context),
    )


def factcheck_get_job(job_id: str) -> RequestSpec:
    return RequestSpec(method="GET", path=f"/api/app/fact-checking/jobs/{job_id}")


def factcheck_list_jobs(skip: int | None, take: int | None) -> RequestSpec:
    return RequestSpec(
        method="GET", path="/api/app/fact-checking/jobs", params={"skip": skip, "take": take}
    )


def factcheck_cancel(job_id: str) -> RequestSpec:
    return RequestSpec(method="POST", path=f"/api/app/fact-checking/jobs/{job_id}/cancel")


# ── Credits & limits ───────────────────────────────────────────────────────────
def image_credit_info() -> RequestSpec:
    return RequestSpec(method="GET", path="/api/app/image-forensics/credit-info")


def audio_credit_info() -> RequestSpec:
    return RequestSpec(method="GET", path="/api/app/voice-analysis/credit-info")


def video_credit_info() -> RequestSpec:
    return RequestSpec(method="GET", path="/api/app/video-forensics/credit-info")


def factcheck_credit_info() -> RequestSpec:
    return RequestSpec(method="GET", path="/api/app/fact-checking/credit-info")


# ── Document ───────────────────────────────────────────────────────────────────
def document_analyze(
    file: FileInput, doc_type: str | None, extract_data: bool | None = None
) -> RequestSpec:
    data: dict[str, str] = {}
    if doc_type is not None:
        data["docType"] = doc_type
    if extract_data is not None:
        data["extractData"] = "true" if extract_data else "false"
    return RequestSpec(
        method="POST",
        path="/api/app/document-analysis/analyze",
        files=[file.to_part("file")],
        data=data,
    )


def document_get(analysis_id: str) -> RequestSpec:
    return RequestSpec(
        method="GET",
        path=f"/api/app/document-analysis/{quote(analysis_id, safe='')}",
    )


def document_page_image(analysis_id: str, page_number: int) -> RequestSpec:
    return RequestSpec(
        method="GET",
        path=(
            f"/api/app/document-analysis/{quote(analysis_id, safe='')}"
            f"/pages/{int(page_number)}/image"
        ),
        binary=True,
    )


def document_evidence(
    analysis_id: str, feature: str, page: int | None, redaction: str | None
) -> RequestSpec:
    return RequestSpec(
        method="GET",
        path=f"/api/app/document-analysis/{quote(analysis_id, safe='')}/evidence",
        params={"feature": feature, "page": page, "redaction": redaction},
        binary=True,
    )


def document_credit_info() -> RequestSpec:
    return RequestSpec(method="GET", path="/api/app/document-analysis/credit-info")
