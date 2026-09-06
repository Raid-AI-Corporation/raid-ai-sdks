# Raid AI SDK

[![npm](https://img.shields.io/npm/v/%40raid_ai%2Fsdk?label=npm%20%40raid_ai%2Fsdk)](https://www.npmjs.com/package/@raid_ai/sdk)
[![PyPI](https://img.shields.io/pypi/v/raidxai?label=PyPI%20raidxai)](https://pypi.org/project/raidxai/)

Official **TypeScript** and **Python** SDKs for the [Raid AI](https://raidxai.com) detection API —
detect AI-generated and manipulated media (images, audio, video), analyze documents for tampering
and AI generation, and fact-check claims against the public record.

| Language | Package | Directory |
|----------|---------|-----------|
| TypeScript / JavaScript | [`@raid_ai/sdk`](https://www.npmjs.com/package/@raid_ai/sdk) | [`typescript/`](typescript/) |
| Python (3.10+) | [`raidxai`](https://pypi.org/project/raidxai/) | [`python/`](python/) |

Full API reference and a live "Try-it" playground: **https://docs.raidxai.com**.

## Use cases

### Clean your data before it poisons your model

Synthetic media is quietly contaminating the datasets everyone scrapes, licenses, and trains on. Train
on it and your models learn from other models' output — degrading quality and collapsing over time. Raid
AI lets you **score every sample and filter the fakes out first**, across all three modalities:

- **Audio** — strip TTS and voice-agent recordings, AI voice clones, and synthetic speech from speech
  corpora, ASR training sets, call transcripts, and voice-authentication enrollment data.
- **Images** — filter GAN- and diffusion-generated images out of scraped or licensed image sets before
  you train, fine-tune, or publish.
- **Video** — flag face-swapped and AI-synthesized clips in datasets and user-generated-content pipelines.

### And more

- **Protect your platform** — flag deepfakes and manipulated uploads at ingestion for trust & safety.
- **Verify before you trust** — fast authenticity checks for newsrooms, OSINT, and moderation teams.
- **Fight fraud & impersonation** — catch synthetic media and cloned voices in KYC and account recovery.
- **Fact-check at scale** — submit a claim and get it checked against the public record.

Every check returns a clear **verdict**, a **confidence score**, and — on detailed plans — a structured
report, so you can automate a decision instead of eyeballing pixels or straining to hear a fake.

## Installation

```bash
npm install @raid_ai/sdk          # TypeScript / JavaScript
pip install raidxai               # Python
```

## Getting started

Create a developer token in the Raid AI dashboard (**Settings → API keys**) and keep it server-side.
Keys carry per-modality scopes (`image`, `audio`, `video`, `fact-check`).

**TypeScript**

```ts
import { RaidClient } from "@raid_ai/sdk";

const raid = new RaidClient({
  apiKey: process.env.RAID_API_KEY!,
  baseUrl: process.env.RAID_API_BASE_URL!,   // required — the Raid AI API base URL
});

const res = await raid.images.processFromUrl("https://example.com/photo.jpg");
console.log(res.images[0]?.verdict, res.images[0]?.confidence);
```

**Python**

```python
from raidxai import RaidClient

with RaidClient(api_key="<your-api-key>", base_url="<raid-ai-api-url>") as raid:
    res = raid.images.process_from_url("https://example.com/photo.jpg")
    print(res.images[0].verdict, res.images[0].confidence)
```

## Usage

### Images (synchronous)

```ts
import { readFileSync } from "node:fs";

const res = await raid.images.process({
  data: readFileSync("suspect.jpg"), fileName: "suspect.jpg", contentType: "image/jpeg",
});
console.log(res.images[0]?.verdict);   // "real" | "ai_generated" | "ai_edited" | "digitally_edited" | "unknown"
```

```python
from raidxai import FileInput

res = raid.images.process(FileInput.from_path("suspect.jpg"))
print(res.images[0].verdict, res.images[0].confidence)
```

### Audio (synchronous)

```ts
import { VoiceWorkflow } from "@raid_ai/sdk";

const res = await raid.audio.process(
  { data: readFileSync("clip.mp3"), fileName: "clip.mp3", contentType: "audio/mpeg" },
  { workflowType: VoiceWorkflow.AiDetectionOnly },
);
console.log(res.isAiDetected, res.detectionConfidence);
```

```python
from raidxai import VoiceWorkflow

res = raid.audio.process(FileInput.from_path("clip.mp3"), workflow_type=VoiceWorkflow.AI_DETECTION_ONLY)
print(res.is_ai_detected, res.detection_confidence, res.detection_classification)
```

The detection confidence is confidence **in the verdict that was reported**, measured as distance
past the decision boundary — not the probability that the audio is AI-generated. `0.5` means the
clip landed on the boundary, and the opposite verdict's confidence is not one minus it. Rank and
shade by it; don't show it to end users as a percentage likelihood.

The response's `metadata` carries the detector's own detail, typed as `VoiceDetectionDetails`
(every field optional, keyed as the detector reports it):

```ts
console.log(res.metadata?.score, res.metadata?.score_basis, res.metadata?.provider);
```

```python
print(res.metadata.score, res.metadata.score_basis, res.metadata.provider)
```

`score` is a 0–1 percentile against the detector's own genuine speech and is the figure to show
(when `score_basis` says `percentile_vs_genuine`); `p_fake` is a raw ranking, not a probability;
`provider` names the detector that produced the verdict, as an open string. Which detector runs is
chosen per account on the Raid AI platform — the SDK exposes no selector.

### Video (asynchronous — submit then poll)

```ts
const job = await raid.video.submitAndWait(
  { data: readFileSync("clip.mp4"), fileName: "clip.mp4", contentType: "video/mp4" },
  { clientDurationSeconds: 42, intervalMs: 3000, timeoutMs: 300_000 },
);
console.log(job.status, job.result?.verdict);
```

```python
job = raid.video.submit_and_wait(
    FileInput.from_path("clip.mp4"), client_duration_seconds=42, interval_seconds=3, timeout_seconds=300,
)
print(job.status, job.result.verdict if job.result else None)
```

### Documents (asynchronous — analyze then poll)

One upload returns both a document-level forensics verdict and per-page tampering /
AI-generation results. A full analysis runs for **minutes**, so `analyze` hands back the record
(usually still `processing`) rather than a finished verdict.

```ts
const analysis = await raid.documents.analyzeAndWait(
  { data: readFileSync("statement.pdf"), fileName: "statement.pdf", contentType: "application/pdf" },
  { docType: "bank_statement", intervalMs: 5_000, timeoutMs: 900_000 },
);
console.log(analysis.fusedVerdict, analysis.fusedProbability);
for (const page of analysis.pages) console.log(page.pageNumber, page.verdict);
```

```python
analysis = raid.documents.analyze_and_wait(
    FileInput.from_path("statement.pdf"), doc_type="bank_statement", interval_seconds=5, timeout_seconds=900,
)
print(analysis.fused_verdict, analysis.fused_probability)
for page in analysis.pages:
    print(page.page_number, page.verdict)
```

Accepted formats are PDF, PNG, JPEG and WebP. Read `page.verdict` (never the raw
`localizedEditing` / `localized_editing` flag) — a wholly AI-generated page was not *edited*, so only
`verdict` folds in the AI-generation check. `pageImage` / `page_image` and `evidence` return the
rasters to draw regions and evidence crops on; `creditInfo` / `credit_info` returns the live
balance and upload limits.

### Fact-checking (asynchronous)

```ts
const job = await raid.factChecking.submitAndWait(
  { data: readFileSync("photo.jpg"), fileName: "photo.jpg", contentType: "image/jpeg" },
  "image",
  { userContext: "Claimed to be from the 2024 election." },
);
console.log(job.result?.summary);
```

```python
job = raid.fact_checking.submit_and_wait(
    FileInput.from_path("photo.jpg"), "image", user_context="Claimed to be from the 2024 election.",
)
print(job.result.summary if job.result else None)
```

Async modalities have no developer webhook — the `submitAndWait` / `submit_and_wait` helpers poll to a
terminal state for you. Python also ships an `AsyncRaidClient` with the same method names.

### Image batch mode (queue now, collect later)

Queue images for analysis in a later scheduled window, at a reduced credit cost. `submitBatch`
returns a batch ID immediately — **no verdicts**. Batch mode is images-only.

```ts
const batch = await raid.images.submitBatch([
  { data: bytesA, fileName: "a.jpg" },
  { data: bytesB, fileName: "b.jpg" },
]);

console.log(batch.batchId, batch.creditsCharged, batch.creditsPerItem);

// Later — poll `isTerminal`, not a status allow-list.
const status = await raid.images.getBatch(batch.batchId!);
if (status.isTerminal) {
  const { items } = await raid.images.batchResults(batch.batchId!);
  for (const item of items ?? []) {
    console.log(item.ordinal, item.fileName, item.result?.verdict);
  }
}
```

Two differences from `process` are structural, not temporary:

- **Turnaround is up to a full processing window** — hours, not seconds. Never put a batch call
  where a person is waiting.
- **Results are basic tier.** `deepAnalysis`, `generators` and `heatmapUrl` are always `null`,
  whatever your plan. Those are realtime-only.

Credits are deducted when the batch is accepted and refunded for any image that ultimately fails.
`cancelBatch` refunds the images still waiting; ones already being analyzed are left to finish.

Match results to your inputs with `ordinal` — the image's position in the original submission.
File names are echoed back but are not guaranteed unique.

`submitBatchAndWait` exists but is rarely what you want: it holds the process open for the whole
window. Prefer submitting, persisting the ID, and collecting later.

## Example: clean a dataset

Walk a folder, keep what comes back real, quarantine the rest:

```python
from pathlib import Path
from raidxai import RaidClient, FileInput, VoiceWorkflow

quarantine = Path("dataset/quarantine"); quarantine.mkdir(exist_ok=True)

with RaidClient(api_key="<your-api-key>", base_url="<raid-ai-api-url>") as raid:
    # Audio: drop AI/cloned voices, keep real human speech.
    for clip in Path("dataset/audio").glob("*.wav"):
        res = raid.audio.process(FileInput.from_path(clip), workflow_type=VoiceWorkflow.AI_DETECTION_ONLY)
        if res.is_ai_detected:
            clip.rename(quarantine / clip.name)

    # Images: keep only real photos, quarantine AI-generated/edited ones.
    for img in Path("dataset/images").glob("*.jpg"):
        res = raid.images.process(FileInput.from_path(img))
        if res.images[0].verdict != "real":
            img.rename(quarantine / img.name)
```

## Credits and limits

Every modality exposes a credit read — `creditInfo()` / `credit_info()` — returning the balance plus
that modality's live limits (per-call cost, max file size, allowed formats, batch or daily caps).
The shapes differ because the pricing does, so there is one call per modality. Read these rather than
hard-coding the defaults; any valid API token may call them and no scope is required.

```ts
const { currentBalance, creditCostPerImage, maxFileSizeMB } = await raid.images.creditInfo();
```

```python
info = raid.images.credit_info()
print(info.current_balance, info.credit_cost_per_image, info.max_file_size_mb)
```

## Error handling

Non-2xx responses surface as a typed `RaidApiError` (`status`, `code`, `message`, `body`, plus
`isAuth` / `isPaymentRequired` / `isRateLimited`). Transient `429`/`5xx` responses retry automatically
with exponential backoff. A `submitAndWait` that never finishes raises `RaidTimeoutError`.

```ts
import { RaidApiError, RaidTimeoutError } from "@raid_ai/sdk";

try {
  await raid.images.process(file);
} catch (err) {
  if (err instanceof RaidApiError) {
    if (err.isAuth) console.error("bad or unscoped token:", err.code);
    else if (err.isPaymentRequired) console.error("out of credits");
    else console.error(err.status, err.code, err.message);
  } else if (err instanceof RaidTimeoutError) {
    console.error("job did not finish in time; last status:", err.lastStatus);
  }
}
```

```python
from raidxai import RaidApiError, RaidTimeoutError

try:
    raid.images.process(file)
except RaidApiError as err:
    if err.is_auth:
        print("bad or unscoped token:", err.code)
    else:
        print(err.status, err.code, err.message)
except RaidTimeoutError as err:
    print("job did not finish in time; last status:", err.last_status)
```

## Configuration

Both clients accept the same options (names are camelCase in TS, snake_case in Python):

| Option | Default | Purpose |
|--------|---------|---------|
| `apiKey` / `api_key` | — (required) | Your developer token. |
| `baseUrl` / `base_url` | — (required) | The Raid AI API base URL. |
| `timeoutMs` / `timeout` | 60s | Per-request timeout. |
| `maxRetries` / `max_retries` | 2 | Retries on `429`/`5xx`/transport errors. |
| `authHeader` / `auth_header` | `"bearer"` | `"bearer"` (Authorization) or `"x-api-key"`. |

## Supported modalities

| Modality | Call | Mode | Returns |
|----------|------|------|---------|
| Images | `images.process` / `processFromUrl` | synchronous | verdict + confidence (+ face analysis) |
| Audio | `audio.process` / `processFromUrl` | synchronous | AI-voice detection + verdict margin + typed detector details (`score`, timeline) |
| Video | `video.submit` / `submitAndWait` / `getJob` / `listJobs` / `cancel` | asynchronous | verdict + confidence |
| Documents | `documents.analyze` / `analyzeAndWait` / `get` / `pageImage` / `evidence` / `creditInfo` | asynchronous | document verdict + per-page tampering / AI results |
| Fact-checking | `factChecking.submit` / `submitAndWait` / `getJob` / `listJobs` / `cancel` | asynchronous | summary + provenance |

Accepted formats and size limits are enforced by the API and documented at
**https://docs.raidxai.com**.

## Documentation

- **API reference & Try-it playground:** https://docs.raidxai.com
- **Per-package guides:** [TypeScript](typescript/README.md) · [Python](python/README.md)

## License

See [LICENSE](LICENSE).
