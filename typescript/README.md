# @raid_ai/sdk

Official TypeScript/JavaScript SDK for the **Raid AI** detection API — detect AI-generated and
manipulated media (images, audio, video), analyze documents for tampering and AI generation, and
fact-check media against the public record.

Works in Node 18+ and the browser. Full API reference: **https://docs.raidxai.com**.

## Install

```bash
npm install @raid_ai/sdk
```

## Authentication

Every request uses a developer token. Create one in the Raid AI dashboard
(**Settings → API keys**) and keep it server-side — never ship it in client code.

```ts
import { RaidClient } from "@raid_ai/sdk";

const raid = new RaidClient({
  apiKey: process.env.RAID_API_KEY!,          // your API key
  baseUrl: process.env.RAID_API_BASE_URL!,    // required — the Raid AI API base URL
  // timeoutMs: 60_000,
  // maxRetries: 2,
  // authHeader: "bearer",                    // or "x-api-key"
});
```

Each API key carries scopes (`image`, `audio`, `video`, `fact-check`) — a call to a modality
your key isn't scoped for returns a typed `403` (`api_key.scope_missing`).

## Usage

### Images (synchronous)

```ts
import { readFileSync } from "node:fs";

const res = await raid.images.process({
  data: readFileSync("suspect.jpg"),
  fileName: "suspect.jpg",
  contentType: "image/jpeg",
});
console.log(res.images[0]?.verdict, res.images[0]?.confidence);

// …or from a URL:
await raid.images.processFromUrl("https://example.com/photo.jpg");
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

`detectionConfidence` is confidence **in the verdict that was reported**, measured as distance
past the decision boundary — not the probability that the audio is AI-generated. `0.5` means the
clip landed on the boundary, and the opposite verdict's confidence is not `1 - detectionConfidence`.
Rank and shade by it; don't show it to end users as a percentage likelihood.

`metadata` carries the detector's own detail, typed as `VoiceDetectionDetails` (every field
optional, keyed as the detector reports it):

```ts
const d = res.metadata;
console.log(d?.provider);        // which detector produced the verdict — an open string, don't hard-code it
console.log(d?.score);           // 0–1 percentile vs the detector's own genuine speech: the figure to show
console.log(d?.score_basis);     // "percentile_vs_genuine" — only read `score` as a percentile when it says so
console.log(d?.chunks?.length);  // per-window timeline, when the detector sends one
```

`p_fake` is a raw ranking, not a probability (`probability_calibrated` is false), so never show
it as a percentage. Which detector runs is chosen per account by the Raid AI platform; the SDK
exposes no selector. The response's `workflowType` is the workflow's *name* (for example
`"AiDetectionOnly"`) even though the request takes the number.

### Video (asynchronous — submit then poll)

```ts
// One-liner: submit and wait for the terminal verdict.
const job = await raid.video.submitAndWait(
  { data: readFileSync("clip.mp4"), fileName: "clip.mp4", contentType: "video/mp4" },
  { clientDurationSeconds: 42, intervalMs: 3000, timeoutMs: 300_000 },
);
console.log(job.status, job.result?.verdict);

// …or drive it yourself:
const { jobId } = await raid.video.submit(file, { clientDurationSeconds: 42 });
const state = await raid.video.getJob(jobId);
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

console.log(analysis.fusedVerdict, analysis.fusedProbability); // "reject", 0.94
for (const page of analysis.pages) {
  console.log(page.pageNumber, page.verdict, page.editedRegions.length);
}

// …or drive it yourself and persist the id:
const started = await raid.documents.analyze(file, { docType: "invoice_po" });
const state = await raid.documents.get(started.id);
```

Accepted formats are PDF, PNG, JPEG and WebP. An image is a single page and has no PDF structure,
so its forensics verdict carries the consistency lane alone.

Four things will bite you if you assume otherwise:

- **Render `page.verdict`, not `page.localizedEditing`.** A wholly AI-generated page reports
  `localizedEditing: false` — nothing on it was *edited*. Only `verdict` folds in the AI check.
- **Two verdict vocabularies.** The document decides with `fusedVerdict`
  (`accept` / `review` / `reject` / `insufficient_quality`); a page describes itself with `verdict`
  (`authentic` / `edited` / `ai_generated`).
- **Two coordinate spaces in one response.** Page regions (`editedRegions`) are original-image
  **pixels** against `pageWidth` / `pageHeight`; forensics finding `bbox` values are **normalized**
  `[x0, y0, x1, y1]` in 0–1. Divide the pixels by the page size to draw both on one overlay.
- **Never re-upload to retry.** A still-`processing` analysis already exists, and a second upload
  is a second charge. Poll `get` with the id you already have.

Fetch the rasters to draw on:

```ts
const { data, contentType } = await raid.documents.pageImage(analysis.id, 2);
const crop = await raid.documents.evidence(analysis.id, { feature: "tampering", page: 2 });
```

`creditInfo()` returns the live balance and upload limits (size ceilings, batch limit, recommended
concurrency) — read those rather than hard-coding the defaults; they are server-side settings.

### Fact-checking (asynchronous)

```ts
const job = await raid.factChecking.submitAndWait(
  { data: readFileSync("photo.jpg"), fileName: "photo.jpg", contentType: "image/jpeg" },
  "image",
  { userContext: "Claimed to be from the 2024 election." },
);
console.log(job.result?.summary, job.result?.provenance);
```

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

## Credits and limits

Every modality exposes a `creditInfo()` read: the current balance plus that modality's live limits —
per-call cost, max file size, allowed formats, and the batch or daily caps where they apply. The
shapes differ because the pricing differs (images are per image, video per analyzed frame, audio per
workflow), so there is one call per modality rather than one shared endpoint.

```ts
const image = await raid.images.creditInfo();
console.log(image.currentBalance, image.creditCostPerImage, image.maxFileSizeMB);

await raid.audio.creditInfo();
await raid.video.creditInfo();
await raid.documents.creditInfo();
await raid.factChecking.creditInfo();
```

Read these rather than hard-coding the defaults — they are account settings and can change without
an SDK release. Any valid API token may call them; no scope is required.

## Errors

Non-2xx responses throw `RaidApiError` with `status`, `code`, `message`, and `body`. Transient
`429`/`5xx` responses are retried automatically with exponential backoff (configurable via `maxRetries`).

```ts
import { RaidApiError, RaidTimeoutError } from "@raid_ai/sdk";

try {
  await raid.images.process(file);
} catch (err) {
  if (err instanceof RaidApiError) {
    if (err.isAuth) console.error("bad or unscoped token:", err.code);
    else if (err.isPaymentRequired) console.error("out of credits:", err.code);
    else console.error(err.status, err.code, err.message);
  } else if (err instanceof RaidTimeoutError) {
    console.error("job did not finish in time; last status:", err.lastStatus);
  }
}
```

## Types

All response and enum types are exported (`ImageForensicsResponse`, `VideoJob`, `Verdict`,
`JobStatus`, …). They are generated from the API's OpenAPI spec, so they track the server contract.

## Development

```bash
npm install
npm run generate:types   # regenerate src/generated/openapi.ts from ../spec/openapi.yaml
npm run typecheck
npm run build            # ESM + CJS + .d.ts via tsup
npm test                 # vitest (fetch mocked)
```

Run the live smoke test against a real tier:

```bash
RAID_API_KEY=<your-api-key> RAID_API_BASE_URL=<raid-ai-api-url> npm test
```
