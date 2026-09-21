# raidxai

Official Python SDK for the **Raid AI** detection API — detect AI-generated and manipulated media
(images, audio, video), analyze documents for tampering and AI generation, and fact-check media
against the public record.

Sync and async clients, Python 3.10+. Full API reference: **https://docs.raidxai.com**.

## Install

```bash
pip install raidxai
```

## Authentication

Every request uses a developer token. Create one in the Raid AI dashboard
(**Settings → API keys**) and keep it server-side — never ship it in client code.

```python
from raidxai import RaidClient, FileInput

raid = RaidClient(
    api_key="<your-api-key>",                 # or os.environ["RAID_API_KEY"]
    # base_url="https://api.raidxai.com",     # optional — defaults to the production API
    # timeout=60.0,
    # max_retries=2,
    # auth_header="bearer",                   # or "x-api-key"
)
```

Each API key carries scopes (`image`, `audio`, `video`, `fact-check`) — a call to a modality
your key isn't scoped for raises `RaidApiError` with a `403` (`api_key.scope_missing`).

## Usage

### Images (synchronous)

```python
res = raid.images.process(FileInput.from_path("suspect.jpg"))
print(res.images[0].verdict, res.images[0].confidence)

# …or from a URL:
raid.images.process_from_url("https://example.com/photo.jpg")
```

### Audio (synchronous)

```python
from raidxai import VoiceWorkflow

res = raid.audio.process(
    FileInput.from_path("clip.mp3"),
    workflow_type=VoiceWorkflow.AI_DETECTION_ONLY,
)
print(res.is_ai_detected, res.detection_confidence)
```

Any file with a decodable audio track is accepted — WAV, MP3, FLAC, M4A/AAC, OGG/Opus, WebM, AMR,
WMA and more, including the soundtrack of an MP4 or WebM video. Acceptance is decided by the file's
content, not its name or content type, and the audio is normalized server-side before analysis.
A file with no audio track fails with `VOICE_ANALYSIS:UNSUPPORTED_FORMAT`; AI detection also needs
at least 2 seconds of audio and refuses clips over the account's limit (35 minutes by default) with
`VOICE_ANALYSIS:CLIP_TOO_SHORT` / `VOICE_ANALYSIS:CLIP_TOO_LONG` — all before any credit is spent.

`detection_confidence` is confidence **in the verdict that was reported**, measured as distance
past the decision boundary — not the probability that the audio is AI-generated. `0.5` means the
clip landed on the boundary, and the opposite verdict's confidence is not
`1 - detection_confidence`. Rank and shade by it; don't show it to end users as a percentage
likelihood.

`metadata` carries the detector's own detail, typed as `VoiceDetectionDetails` (every field
optional, keyed as the detector reports it):

```python
d = res.metadata
print(d.provider)        # which detector produced the verdict — an open string, don't hard-code it
print(d.score)           # 0–1 percentile vs the detector's own genuine speech: the figure to show
print(d.score_basis)     # "percentile_vs_genuine" — only read `score` as a percentile when it says so
print(len(d.chunks or []))  # per-window timeline, when the detector sends one
print(d.model_extra)     # keys the spec leaves untyped ride through here
```

`p_fake` is a raw ranking, not a probability (`probability_calibrated` is false), so never show
it as a percentage. Which detector runs is chosen per account by the Raid AI platform; the SDK
exposes no selector. The response's `workflow_type` is the workflow's *name* (for example
`"AiDetectionOnly"`) even though the request takes the number.

### Video (asynchronous — submit then poll)

```python
# One call: submit and wait for the terminal verdict.
job = raid.video.submit_and_wait(
    FileInput.from_path("clip.mp4"),
    client_duration_seconds=42,
    interval_seconds=3,
    timeout_seconds=300,
)
print(job.status, job.result.verdict if job.result else None)

# …or drive it yourself:
submitted = raid.video.submit(FileInput.from_path("clip.mp4"), client_duration_seconds=42)
state = raid.video.get_job(submitted.job_id)
```

### Documents (asynchronous — analyze then poll)

One upload returns both a document-level forensics verdict and per-page tampering /
AI-generation results. A full analysis runs for **minutes**, so `analyze` hands back the record
(usually still `processing`) rather than a finished verdict.

```python
analysis = raid.documents.analyze_and_wait(
    FileInput.from_path("statement.pdf"),
    doc_type="bank_statement",
    interval_seconds=5,
    timeout_seconds=900,
)

print(analysis.fused_verdict, analysis.fused_probability)  # "reject", 0.94
for page in analysis.pages:
    print(page.page_number, page.verdict, len(page.edited_regions))

# …or drive it yourself and persist the id:
started = raid.documents.analyze(FileInput.from_path("invoice.pdf"), doc_type="invoice_po")
state = raid.documents.get(str(started.id))
```

Accepted formats are PDF, PNG, JPEG and WebP. An image is a single page and has no PDF structure,
so its forensics verdict carries the consistency lane alone.

Four things will bite you if you assume otherwise:

- **Render `page.verdict`, not `page.localized_editing`.** A wholly AI-generated page reports
  `localized_editing=False` — nothing on it was *edited*. Only `verdict` folds in the AI check.
- **Two verdict vocabularies.** The document decides with `fused_verdict`
  (`accept` / `review` / `reject` / `insufficient_quality`); a page describes itself with `verdict`
  (`authentic` / `edited` / `ai_generated`).
- **Two coordinate spaces in one response.** Page regions (`edited_regions`) are original-image
  **pixels** against `page_width` / `page_height`; forensics finding `bbox` values are
  **normalized** `[x0, y0, x1, y1]` in 0–1. Divide the pixels by the page size to draw both on one
  overlay.
- **Never re-upload to retry.** A still-`processing` analysis already exists, and a second upload
  is a second charge. Poll `get` with the id you already have.

Three document types also get their **data extracted and checked** — `commercial_registry`,
`tax_card` and `utility_bill`, only when you submit that `doc_type`. The result is a second status
beside the verdict, never part of it:

```python
import time
from raidxai import DocumentDataStatus

record = raid.documents.analyze_and_wait(FileInput.from_path("card.pdf"), doc_type="tax_card")
# analyze_and_wait returns on the VERDICT; extraction lands afterwards.
while record.data_status is DocumentDataStatus.pending:
    time.sleep(3)
    record = raid.documents.get(str(record.id))
if record.data_status is DocumentDataStatus.verified:
    print(record.extraction.fields["tax_id"])
elif record.data_status is DocumentDataStatus.in_review:
    print(record.extraction.reasons)
```

`data_status` is `pending` / `verified` / `in_review` / `failed`, or `None` with
`extraction_skip_reason` saying why (`unsupported_type`, `declined_at_upload`, `disabled`). Pass
`extract_data=False` to skip extraction for an upload you only want a verdict on.

Fetch the rasters to draw on:

```python
image = raid.documents.page_image(str(analysis.id), 2)   # .data bytes + .content_type
crop = raid.documents.evidence(str(analysis.id), feature="tampering", page=2)
```

`credit_info()` returns the live balance and upload limits (size ceilings, batch limit, recommended
concurrency) — read those rather than hard-coding the defaults; they are server-side settings.

### Fact-checking (asynchronous)

```python
job = raid.fact_checking.submit_and_wait(
    FileInput.from_path("photo.jpg"),
    "image",
    user_context="Claimed to be from the 2024 election.",
)
print(job.result.summary if job.result else None)
```

### Image batch mode (queue now, collect later)

Queue images for analysis in a later scheduled window, at a reduced credit cost. `submit_batch`
returns a batch ID immediately — **no verdicts**. Batch mode is images-only.

```python
batch = client.images.submit_batch([
    FileInput.from_path("a.jpg"),
    FileInput.from_path("b.jpg"),
])

print(batch.batch_id, batch.credits_charged, batch.credits_per_item)

# Later — poll `is_terminal`, not a status allow-list.
status = client.images.get_batch(str(batch.batch_id))
if status.is_terminal:
    page = client.images.batch_results(str(batch.batch_id))
    for item in page.items or []:
        print(item.ordinal, item.file_name, item.result.verdict if item.result else None)
```

Two differences from `process` are structural, not temporary:

- **Turnaround is up to a full processing window** — hours, not seconds. Never put a batch call
  where a person is waiting.
- **Results are basic tier.** `deep_analysis`, `generators` and `heatmap_url` are always `None`,
  whatever your plan. Those are realtime-only.

Credits are deducted when the batch is accepted and refunded for any image that ultimately fails.
`cancel_batch` refunds the images still waiting; ones already being analyzed are left to finish.

Match results to your inputs with `ordinal` — the image's position in the original submission.
File names are echoed back but are not guaranteed unique.

`submit_batch_and_wait` exists but is rarely what you want: it holds the process open for the whole
window. Prefer submitting, persisting the ID, and collecting later.

## Credits and limits

Every modality exposes a `credit_info()` read: the current balance plus that modality's live limits —
per-call cost, max file size, allowed formats, and the batch or daily caps where they apply. The
shapes differ because the pricing differs (images are per image, video per analyzed frame, audio per
workflow), so there is one call per modality rather than one shared endpoint. Audio is the one
modality with no format list: `allowed_file_formats` is always `"*"` (kept for older clients) and
`accepts_any_audio` is `True`.

```python
image = raid.images.credit_info()
print(image.current_balance, image.credit_cost_per_image, image.max_file_size_mb)

raid.audio.credit_info()
raid.video.credit_info()
raid.documents.credit_info()
raid.fact_checking.credit_info()
```

Read these rather than hard-coding the defaults — they are account settings and can change without
an SDK release. Any valid API token may call them; no scope is required.

## Async

Every resource has an async twin on `AsyncRaidClient` with the same method names:

```python
import asyncio
from raidxai import AsyncRaidClient, FileInput

async def main():
    async with AsyncRaidClient(api_key="<your-api-key>") as raid:
        res = await raid.images.process(FileInput.from_path("photo.jpg"))
        print(res.images[0].verdict)

asyncio.run(main())
```

## Errors

Non-2xx responses raise `RaidApiError` (`.status`, `.code`, `.message`, `.body`, plus `.is_auth` /
`.is_payment_required` / `.is_rate_limited`). Transient `429`/`5xx` responses are retried automatically
with exponential backoff (`max_retries`). A `submit_and_wait` that never finishes raises `RaidTimeoutError`.

```python
from raidxai import RaidApiError, RaidTimeoutError

try:
    raid.images.process(file)
except RaidApiError as err:
    if err.is_auth:
        print("bad or unscoped token:", err.code)
    elif err.is_payment_required:
        print("out of credits:", err.code)
    else:
        print(err.status, err.code, err.message)
except RaidTimeoutError as err:
    print("job did not finish in time; last status:", err.last_status)
```

## Types

Response models are Pydantic v2 classes generated from the API's OpenAPI spec (`ImageForensicsResponse`,
`VideoJob`, `Verdict`, `JobStatus`, …), so attributes are snake_case and tracked against the server contract.

## Development

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
./scripts/generate.sh   # regenerate src/raidxai/_generated/models.py from ../spec/openapi.yaml
ruff check .
pytest
```

Run the live smoke test against a real tier (auto-skips without the key):

```bash
RAID_API_KEY=<your-api-key> RAID_API_BASE_URL=<raid-ai-api-url> pytest tests/test_live_smoke.py
```
