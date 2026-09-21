from __future__ import annotations

import httpx
import pytest

from conftest import TEST_BASE_URL, async_client, make_response, sync_client
from raidxai import (
    BinaryResponse,
    DocumentDataStatus,
    DocumentStatus,
    DocumentType,
    FileInput,
    RaidApiError,
    RaidClient,
    RaidTimeoutError,
    VoiceWorkflow,
)
from raidxai.client import DEFAULT_BASE_URL

JOB_ID = "9a8b7c6d-1234-5678-90ab-cdef12345678"

IMAGE_OK = {
    "images": [
        {
            "fileName": "p.jpg",
            "verdict": "ai_generated",
            "confidence": 0.97,
            "isManipulated": True,
            "creditsUsed": 1,
            "processingTimeMs": 10,
            "createdAt": "2026-01-01T00:00:00Z",
        }
    ],
    "totalCreditsUsed": 1,
    "totalProcessingTimeMs": 10,
    "isSuccessful": True,
    "hasDetailedReport": False,
}


def png_file() -> FileInput:
    return FileInput(data=b"\x89PNG\r\n", file_name="p.png", content_type="image/png")


# ── construction ──────────────────────────────────────────────────────────────
def test_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        RaidClient(api_key="", base_url="https://api.example.test")


def test_defaults_base_url_to_production():
    client = RaidClient(api_key="test-key")
    assert str(client._http.base_url) == DEFAULT_BASE_URL


def test_uses_base_url_for_route():
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        return make_response(200, IMAGE_OK)

    client = sync_client(handler)
    client.images.process_from_url("https://example.com/a.jpg")
    assert seen["url"] == "https://api.example.test/api/app/image-forensics/process-from-url"


# ── auth headers ──────────────────────────────────────────────────────────────
def test_bearer_header_by_default():
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers.get("authorization", "")
        return make_response(200, IMAGE_OK)

    sync_client(handler).images.process_from_url("https://x/y.jpg")
    assert seen["auth"] == "Bearer test-key"


def test_x_api_key_header():
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["xkey"] = req.headers.get("x-api-key", "")
        seen["auth"] = req.headers.get("authorization", "")
        return make_response(200, IMAGE_OK)

    sync_client(handler, auth_header="x-api-key").images.process_from_url("https://x/y.jpg")
    assert seen["xkey"] == "test-key"
    assert seen["auth"] == ""


# ── error mapping ─────────────────────────────────────────────────────────────
def test_error_envelope_unwrapped():
    def handler(_req: httpx.Request) -> httpx.Response:
        return make_response(
            400,
            {"error": {"code": "IMAGE_FORENSICS:FILE_TOO_LARGE", "message": "too big"}},
        )

    with pytest.raises(RaidApiError) as exc:
        sync_client(handler).images.process_from_url("https://x/y.jpg")
    assert exc.value.status == 400
    assert exc.value.code == "IMAGE_FORENSICS:FILE_TOO_LARGE"
    assert exc.value.message == "too big"


def test_scope_error_is_auth():
    def handler(_req: httpx.Request) -> httpx.Response:
        return make_response(
            403, {"error": {"code": "api_key.scope_missing", "message": "no scope"}}
        )

    with pytest.raises(RaidApiError) as exc:
        sync_client(handler).images.process_from_url("https://x/y.jpg")
    assert exc.value.is_auth
    assert exc.value.code == "api_key.scope_missing"


def test_payment_required():
    def handler(_req: httpx.Request) -> httpx.Response:
        return make_response(402, {"code": "USER_CREDIT_LIMIT_REACHED", "message": "no credits"})

    with pytest.raises(RaidApiError) as exc:
        sync_client(handler).images.process_from_url("https://x/y.jpg")
    assert exc.value.is_payment_required
    assert exc.value.message == "no credits"


def test_raw_string_error_body():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="plain failure")

    with pytest.raises(RaidApiError) as exc:
        sync_client(handler).images.process_from_url("https://x/y.jpg")
    assert exc.value.message == "plain failure"


# ── retry ──────────────────────────────────────────────────────────────────────
def test_retries_5xx_then_succeeds():
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return make_response(200, IMAGE_OK)

    client = sync_client(handler, max_retries=3)
    res = client.images.process_from_url("https://x/y.jpg")
    assert calls["n"] == 3
    assert res.is_successful


def test_no_retry_on_400():
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return make_response(400, {"error": {"code": "X", "message": "bad"}})

    with pytest.raises(RaidApiError):
        sync_client(handler, max_retries=3).images.process_from_url("https://x/y.jpg")
    assert calls["n"] == 1


# ── multipart ──────────────────────────────────────────────────────────────────
def test_multipart_image_upload():
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["content_type"] = req.headers.get("content-type", "")
        seen["body"] = req.content
        return make_response(200, IMAGE_OK)

    sync_client(handler).images.process(png_file(), external_id="corr-1")
    assert "multipart/form-data" in seen["content_type"]
    assert b'name="imageFiles"' in seen["body"]
    assert b'name="input.ExternalId"' in seen["body"]
    assert b"corr-1" in seen["body"]


def test_response_parses_into_model():
    res = sync_client(lambda _r: make_response(200, IMAGE_OK)).images.process(png_file())
    assert res.images[0].verdict.value == "ai_generated"
    assert res.images[0].confidence == 0.97


def test_voice_workflow_constant_sent():
    seen: dict[str, bytes] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = req.content
        return make_response(
            200,
            {
                "isSuccessful": True,
                "workflowType": "AiDetectionOnly",
                "processingTimeMs": 1,
                "creditsUsed": 1,
            },
        )

    sync_client(handler).audio.process(
        FileInput(data=b"\x00", file_name="a.mp3", content_type="audio/mpeg"),
        workflow_type=VoiceWorkflow.AI_DETECTION_ONLY,
    )
    assert b'name="input.WorkflowType"' in seen["body"]
    assert b"4" in seen["body"]


# A realistic detection response as the platform serves it: ``workflowType`` is the workflow's
# NAME on the wire (the request takes the number), and ``metadata`` carries the detector's detail.
VOICE_OK = {
    "isSuccessful": True,
    "errorMessage": None,
    "workflowType": "AiDetectionOnly",
    "isAiDetected": True,
    "detectionConfidence": 0.93,
    "detectionClassification": "fake",
    "processingTimeMs": 2110,
    "creditsUsed": 1,
    "metadata": {
        "provider": "raid_1b",
        "detection_method": "raid_1b_llr_global_mean",
        "score": 0.994,
        "score_basis": "percentile_vs_genuine",
        "p_fake": 0.31,
        "probability_calibrated": False,
        "threshold_calibrated": True,
        "threshold_global_tau": -4.93,
        "threshold_partial_tau": -3.03,
        "threshold_fired_global": True,
        "low_confidence": False,
        "chunks": [
            {
                "index": 0,
                "chunk": "0-4s",
                "result": "fake",
                "confidence": 0.91,
                "score": 0.29,
                "start_s": 0,
                "end_s": 4,
                "llr": -7.1,
            }
        ],
        "settings": {"hop_s": 2.0},
    },
}


def test_audio_response_workflow_type_is_a_name():
    res = sync_client(lambda req: make_response(200, VOICE_OK)).audio.process_from_url(
        "https://x/y.mp3"
    )
    assert res.workflow_type == "AiDetectionOnly"
    assert res.is_ai_detected is True


def test_audio_process_metadata_typed():
    res = sync_client(lambda req: make_response(200, VOICE_OK)).audio.process(
        FileInput(data=b"\x00", file_name="a.wav", content_type="audio/wav")
    )
    d = res.metadata
    assert d is not None
    assert d.provider == "raid_1b"
    assert d.score == 0.994
    assert d.score_basis == "percentile_vs_genuine"
    assert d.probability_calibrated is False
    assert d.threshold_partial_tau == -3.03
    assert d.chunks is not None and d.chunks[0].llr == -7.1
    # Keys the spec leaves untyped still ride through.
    assert d.model_extra is not None and d.model_extra["settings"] == {"hop_s": 2.0}


# ── async + poll ────────────────────────────────────────────────────────────────
def _video_job(status: str) -> dict:
    return {
        "id": JOB_ID,
        "fileName": "c.mp4",
        "status": status,
        "progress": 100,
        "creditsReserved": 4,
        "creditsUsed": 4,
        "processingTimeMs": 1,
        "createdAt": "2026-01-01T00:00:00Z",
    }


def test_submit_and_wait_polls_to_terminal():
    statuses = iter(["Queued", "Processing", "Completed"])

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return make_response(200, {"jobId": JOB_ID, "creditsReserved": 4})
        return make_response(200, _video_job(next(statuses, "Completed")))

    job = sync_client(handler).video.submit_and_wait(
        FileInput(data=b"\x00", file_name="c.mp4", content_type="video/mp4"),
        client_duration_seconds=10,
        interval_seconds=0.001,
        timeout_seconds=5,
    )
    assert job.status.value == "Completed"


def test_submit_and_wait_times_out():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return make_response(200, {"jobId": JOB_ID, "creditsReserved": 4})
        return make_response(200, _video_job("Processing"))

    with pytest.raises(RaidTimeoutError):
        sync_client(handler).video.submit_and_wait(
            FileInput(data=b"\x00", file_name="c.mp4", content_type="video/mp4"),
            interval_seconds=0.001,
            timeout_seconds=0.005,
        )


def test_list_normalizes_bare_array():
    body = [_video_job("Completed"), _video_job("Failed")]
    page = sync_client(lambda _r: make_response(200, body)).video.list_jobs()
    assert page.total_count == 2
    assert len(page.items) == 2


def test_list_normalizes_envelope():
    page = sync_client(
        lambda _r: make_response(200, {"items": [_video_job("Completed")], "totalCount": 42})
    ).video.list_jobs()
    assert page.total_count == 42


async def test_async_image_process():
    async with async_client(lambda _r: make_response(200, IMAGE_OK)) as raid:
        res = await raid.images.process(png_file())
    assert res.images[0].verdict.value == "ai_generated"


async def test_async_submit_and_wait():
    statuses = iter(["Processing", "Completed"])

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return make_response(200, {"jobId": JOB_ID, "creditsReserved": 1})
        return make_response(200, _video_job(next(statuses, "Completed")))

    async with async_client(handler) as raid:
        job = await raid.video.submit_and_wait(
            FileInput(data=b"\x00", file_name="c.mp4", content_type="video/mp4"),
            interval_seconds=0.001,
            timeout_seconds=5,
        )
    assert job.status.value == "Completed"


# --- image batch mode -------------------------------------------------------


def test_submit_batch_posts_every_file():
    # Real UUIDs throughout: the spec declares batchId as format uuid, so the generated model
    # validates it. A placeholder id here would fail for the wrong reason.
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = request.content
        return make_response(
            202,
            {
                "batchId": "8f14e45f-ceea-467a-9f38-1a2b3c4d5e6f",
                "status": "Accepted",
                "itemCount": 2,
                "creditsCharged": 32,
                "creditsPerItem": 16,
                "realtimeCreditsPerItem": 20,
            },
        )

    client = sync_client(handler)
    res = client.images.submit_batch(
        [
            FileInput(data=b"\x01", file_name="a.jpg"),
            FileInput(data=b"\x02", file_name="b.jpg"),
        ],
        external_id="job-7",
    )

    assert str(res.batch_id) == "8f14e45f-ceea-467a-9f38-1a2b3c4d5e6f"
    assert res.credits_per_item == 16
    assert captured["url"].endswith("/api/app/image-forensics/batches")
    # Both files travel under the same repeated field the realtime endpoint binds.
    assert captured["body"].count(b'name="imageFiles"') == 2
    assert b"job-7" in captured["body"]


def test_submit_batch_rejects_empty_list():
    calls = []

    def handler(request):
        calls.append(request)
        return make_response(202, {})

    client = sync_client(handler)
    with pytest.raises(ValueError, match="at least one image"):
        client.images.submit_batch([])

    # The guard exists so an empty call costs neither credits nor a round trip.
    assert calls == []


def test_submit_batch_and_wait_polls_on_is_terminal():
    """A status the SDK has never seen must still end the loop when the server says terminal."""
    bodies = [
        {
            "batchId": "8f14e45f-ceea-467a-9f38-1a2b3c4d5e6f",
            "status": "Accepted",
            "isTerminal": False,
        },
        {
            "batchId": "8f14e45f-ceea-467a-9f38-1a2b3c4d5e6f",
            "status": "Completed",
            "isTerminal": True,
        },
    ]
    state = {"i": 0}

    def handler(request):
        if "/batches/" in str(request.url):
            body = bodies[min(state["i"], len(bodies) - 1)]
            state["i"] += 1
            return make_response(200, body)
        return make_response(
            202,
            {
                "batchId": "8f14e45f-ceea-467a-9f38-1a2b3c4d5e6f",
                "status": "Accepted",
                "itemCount": 1,
            },
        )

    client = sync_client(handler)
    batch = client.images.submit_batch_and_wait(
        [FileInput(data=b"\x01", file_name="a.jpg")],
        interval_seconds=0.01,
    )

    assert batch.is_terminal is True


def test_batch_id_is_url_quoted():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return make_response(200, {"cancelledItems": 3, "creditsRefunded": 48})

    client = sync_client(handler)
    client.images.cancel_batch("a/b?c")

    assert "/batches/a%2Fb%3Fc/cancel" in captured["url"]


async def test_async_submit_batch():
    def handler(request):
        return make_response(
            202,
            {
                "batchId": "3c0f7d2a-1b44-4e8a-9c31-77aa55bb99cc",
                "status": "Accepted",
                "itemCount": 1,
            },
        )

    client = async_client(handler)
    res = await client.images.submit_batch([FileInput(data=b"\x01", file_name="a.jpg")])
    assert str(res.batch_id) == "3c0f7d2a-1b44-4e8a-9c31-77aa55bb99cc"


# ── document analysis ─────────────────────────────────────────────────────────
DOC_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


def _analysis(status: str) -> dict:
    """Minimal record; the resource only branches on ``id`` + ``status``."""
    return {
        "id": DOC_ID,
        "docId": "t-abc-u123",
        "mediaKind": "pdf",
        "docType": "",
        "status": status,
        "forensicsStatus": status,
        "pagesStatus": status,
        "fusedVerdict": "reject" if status == "completed" else "",
        "fusedProbability": 0.0,
        "fusionRationale": "",
        "pagesTotal": 1,
        "pagesCompleted": 1 if status == "completed" else 0,
        "pagesFailed": 0,
        "creditsUsed": 1,
        "pages": [],
    }


def pdf_file() -> FileInput:
    return FileInput(data=b"%PDF-1.7", file_name="statement.pdf", content_type="application/pdf")


def test_document_analyze_uploads_file_and_doc_type():
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = req.content
        # 202 is the expected outcome, not an error.
        return make_response(202, _analysis("processing"))

    res = sync_client(handler).documents.analyze(pdf_file(), doc_type=DocumentType.bank_statement)

    assert seen["url"] == f"{TEST_BASE_URL}/api/app/document-analysis/analyze"
    assert b'name="file"' in seen["body"]  # type: ignore[operator]
    assert b"bank_statement" in seen["body"]  # type: ignore[operator]
    assert res.status is DocumentStatus.processing
    assert str(res.id) == DOC_ID


def test_document_analyze_accepts_a_plain_doc_type_string():
    seen: dict[str, bytes] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = req.content
        return make_response(202, _analysis("processing"))

    sync_client(handler).documents.analyze(pdf_file(), doc_type="plane_ticket")
    assert b"plane_ticket" in seen["body"]


def test_document_analyze_sends_extract_data_only_when_given():
    bodies: list[bytes] = []

    def handler(req: httpx.Request) -> httpx.Response:
        bodies.append(req.content)
        return make_response(202, _analysis("processing"))

    client = sync_client(handler)
    client.documents.analyze(pdf_file(), doc_type="tax_card")
    client.documents.analyze(pdf_file(), doc_type="tax_card", extract_data=False)

    assert b"extractData" not in bodies[0]
    assert b'name="extractData"' in bodies[1] and b"false" in bodies[1]


def test_document_record_carries_the_extraction_leg():
    body = _analysis("completed")
    body["dataStatus"] = "in_review"
    body["extractionSkipReason"] = None
    body["extraction"] = {
        "status": "completed",
        "fields": {"tax_id": "300123456"},
        "fieldChecks": {"tax_id": {"status": "ok"}},
        "reasons": [],
        "pages": [],
        "truncated": False,
    }
    res = sync_client(lambda _req: make_response(200, body)).documents.get(DOC_ID)

    assert res.data_status is DocumentDataStatus.in_review
    assert res.extraction is not None
    assert res.extraction.fields == {"tax_id": "300123456"}
    assert res.extraction.field_checks["tax_id"].status == "ok"  # type: ignore[index]


def test_document_analyze_and_wait_polls_to_terminal():
    statuses = iter(["processing", "processing", "completed"])
    urls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        urls.append(str(req.url))
        if req.method == "POST":
            return make_response(202, _analysis("processing"))
        return make_response(200, _analysis(next(statuses, "completed")))

    done = sync_client(handler).documents.analyze_and_wait(
        pdf_file(), interval_seconds=0.001, timeout_seconds=5
    )

    assert done.status is DocumentStatus.completed
    assert urls[1] == f"{TEST_BASE_URL}/api/app/document-analysis/{DOC_ID}"


def test_document_analyze_and_wait_skips_polling_when_already_terminal():
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.method)
        return make_response(200, _analysis("completed"))

    done = sync_client(handler).documents.analyze_and_wait(pdf_file(), interval_seconds=0.001)

    assert done.status is DocumentStatus.completed
    assert calls == ["POST"]  # no wasted poll


def test_document_analyze_and_wait_times_out():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return make_response(202, _analysis("processing"))
        return make_response(200, _analysis("processing"))

    with pytest.raises(RaidTimeoutError):
        sync_client(handler).documents.analyze_and_wait(
            pdf_file(), interval_seconds=0.001, timeout_seconds=0.005
        )


def test_document_page_image_returns_bytes():
    png = b"\x89PNG\r\n\x1a\n"
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["accept"] = req.headers.get("accept")
        return httpx.Response(200, content=png, headers={"content-type": "image/png"})

    image = sync_client(handler).documents.page_image(DOC_ID, 2)

    assert seen["url"] == f"{TEST_BASE_URL}/api/app/document-analysis/{DOC_ID}/pages/2/image"
    assert seen["accept"] == "*/*"
    assert isinstance(image, BinaryResponse)
    assert image.data == png
    assert image.content_type == "image/png"


def test_document_binary_endpoint_maps_json_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return make_response(404, {"error": {"code": "NOT_FOUND", "message": "Page not found."}})

    with pytest.raises(RaidApiError) as excinfo:
        sync_client(handler).documents.page_image(DOC_ID, 9)

    assert excinfo.value.status == 404
    assert excinfo.value.code == "NOT_FOUND"


def test_document_evidence_sends_lane_page_and_redaction():
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        return httpx.Response(200, content=b"\x01", headers={"content-type": "image/png"})

    sync_client(handler).documents.evidence(
        DOC_ID, feature="tampering", page=2, redaction="redaction-p2-a.png"
    )

    assert "feature=tampering" in seen["url"]
    assert "page=2" in seen["url"]
    assert "redaction=redaction-p2-a.png" in seen["url"]


def test_document_credit_info_reads_server_limits():
    body = {
        "currentBalance": 12,
        "creditCostPerDocument": 1,
        "maxBatchFiles": 5,
        "analyzeConcurrency": 3,
        "maxFileSizeMB": 40,
        "maxImageSizeMB": 10,
        "userHeadroomRemaining": None,
        "canUseFeature": True,
    }
    info = sync_client(lambda _r: make_response(200, body)).documents.credit_info()

    assert info.max_file_size_mb == 40
    assert info.user_headroom_remaining is None


def test_document_analysis_id_is_url_quoted():
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        return make_response(200, _analysis("completed"))

    sync_client(handler).documents.get("a/b")
    assert "/document-analysis/a%2Fb" in seen["url"]


async def test_async_document_analyze_and_wait():
    statuses = iter(["processing", "completed"])

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return make_response(202, _analysis("processing"))
        return make_response(200, _analysis(next(statuses, "completed")))

    async with async_client(handler) as raid:
        done = await raid.documents.analyze_and_wait(
            pdf_file(), interval_seconds=0.001, timeout_seconds=5
        )

    assert done.status is DocumentStatus.completed


async def test_async_document_page_image_returns_bytes():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})

    async with async_client(handler) as raid:
        image = await raid.documents.page_image(DOC_ID, 1)

    assert image.data == b"\x89PNG"


# ── credits & limits (one read per modality) ──────────────────────────────────
def test_credit_info_routes_per_modality():
    """Each modality reads its own route — the shapes differ, so they can't share one."""
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return make_response(
            200,
            {
                "currentBalance": 480,
                "tenantCredits": 480,
                "creditCostPerImage": 1,
                "creditCostPerFrame": 1,
                "maxFileSizeMB": 50,
                "allowedFileFormats": "jpg,png",
                "acceptsAnyAudio": True,
                "canUseFeature": True,
            },
        )

    raid = sync_client(handler)
    assert raid.images.credit_info().credit_cost_per_image == 1
    audio = raid.audio.credit_info()
    assert audio.tenant_credits == 480
    # Audio accepts any decodable file; the flag is what new clients should read, the
    # deprecated extension list keeps deserializing for old ones — and reading it warns.
    assert audio.accepts_any_audio is True
    with pytest.warns(DeprecationWarning):
        assert isinstance(audio.allowed_file_formats, str)
    assert raid.video.credit_info().credit_cost_per_frame == 1
    assert raid.fact_checking.credit_info().current_balance == 480

    assert seen == [
        f"{TEST_BASE_URL}/api/app/image-forensics/credit-info",
        f"{TEST_BASE_URL}/api/app/voice-analysis/credit-info",
        f"{TEST_BASE_URL}/api/app/video-forensics/credit-info",
        f"{TEST_BASE_URL}/api/app/fact-checking/credit-info",
    ]


async def test_async_credit_info():
    body = {
        "currentBalance": 12,
        "maxFileSizeMB": 50,
        "allowedFileFormats": "jpg",
        "canUseFeature": False,
    }
    async with async_client(lambda _r: make_response(200, body)) as raid:
        info = await raid.fact_checking.credit_info()
    assert info.can_use_feature is False
