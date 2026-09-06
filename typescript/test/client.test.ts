import { describe, it, expect, vi } from "vitest";
import { RaidClient, RaidApiError, RaidTimeoutError, type FetchLike } from "../src/index.js";

/** Build a fetch stub that returns a JSON response, capturing the calls it receives. */
function jsonFetch(status: number, body: unknown, headers: Record<string, string> = {}): {
  fetch: FetchLike;
  calls: Array<{ url: string; init?: RequestInit }>;
} {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetch: FetchLike = async (url, init) => {
    calls.push({ url, init });
    return new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json", ...headers },
    });
  };
  return { fetch, calls };
}

// Neutral base URL for tests (a reserved .test TLD — not a real host).
const TEST_BASE_URL = "https://api.example.test";

function makeClient(fetch: FetchLike, overrides = {}) {
  return new RaidClient({ apiKey: "test-key-123", baseUrl: TEST_BASE_URL, fetch, maxRetries: 0, ...overrides });
}

describe("RaidClient construction", () => {
  it("requires an apiKey", () => {
    // @ts-expect-error — intentionally missing apiKey
    expect(() => new RaidClient({ baseUrl: TEST_BASE_URL, fetch: jsonFetch(200, {}).fetch })).toThrow(/apiKey/);
  });

  it("requires a baseUrl", () => {
    // @ts-expect-error — intentionally missing baseUrl
    expect(() => new RaidClient({ apiKey: "test-key", fetch: jsonFetch(200, {}).fetch })).toThrow(/baseUrl/);
  });

  it("uses the provided base URL for routing", async () => {
    const { fetch, calls } = jsonFetch(200, { images: [], totalCreditsUsed: 0, totalProcessingTimeMs: 0, isSuccessful: true, hasDetailedReport: false });
    const raid = makeClient(fetch);
    await raid.images.processFromUrl("https://example.com/a.jpg");
    expect(calls[0]?.url).toBe(`${TEST_BASE_URL}/api/app/image-forensics/process-from-url`);
  });

  it("strips a trailing slash from the base URL", async () => {
    const { fetch, calls } = jsonFetch(200, {});
    const raid = makeClient(fetch, { baseUrl: `${TEST_BASE_URL}/` });
    await raid.video.getJob("abc");
    expect(calls[0]?.url).toBe(`${TEST_BASE_URL}/api/app/video-forensics/jobs/abc`);
  });
});

describe("auth headers", () => {
  it("sends a bearer token by default", async () => {
    const { fetch, calls } = jsonFetch(200, {});
    await makeClient(fetch).video.getJob("j1");
    const headers = calls[0]?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-key-123");
  });

  it("can send X-Api-Key instead", async () => {
    const { fetch, calls } = jsonFetch(200, {});
    await makeClient(fetch, { authHeader: "x-api-key" }).video.getJob("j1");
    const headers = calls[0]?.init?.headers as Record<string, string>;
    expect(headers["X-Api-Key"]).toBe("test-key-123");
    expect(headers.Authorization).toBeUndefined();
  });
});

describe("error mapping", () => {
  it("unwraps the { error: { code, message } } envelope", async () => {
    const { fetch } = jsonFetch(400, { error: { code: "IMAGE_FORENSICS:FILE_TOO_LARGE", message: "File too large." } });
    const raid = makeClient(fetch);
    await expect(raid.images.processFromUrl("https://x/y.jpg")).rejects.toMatchObject({
      name: "RaidApiError",
      status: 400,
      code: "IMAGE_FORENSICS:FILE_TOO_LARGE",
      message: "File too large.",
    });
  });

  it("maps a 403 scope error and flags isAuth", async () => {
    const { fetch } = jsonFetch(403, { error: { code: "api_key.scope_missing", message: "Not authorized for the image scope." } });
    try {
      await makeClient(fetch).images.processFromUrl("https://x/y.jpg");
      throw new Error("expected throw");
    } catch (err) {
      expect(err).toBeInstanceOf(RaidApiError);
      const e = err as RaidApiError;
      expect(e.isAuth).toBe(true);
      expect(e.code).toBe("api_key.scope_missing");
    }
  });

  it("flags 402 as payment required", async () => {
    const { fetch } = jsonFetch(402, { code: "USER_CREDIT_LIMIT_REACHED", message: "Credit limit reached." });
    try {
      await makeClient(fetch).images.processFromUrl("https://x/y.jpg");
      throw new Error("expected throw");
    } catch (err) {
      const e = err as RaidApiError;
      expect(e.isPaymentRequired).toBe(true);
      expect(e.message).toBe("Credit limit reached.");
    }
  });

  it("handles a raw string error body", async () => {
    const fetch: FetchLike = async () => new Response("something broke", { status: 400, headers: { "content-type": "text/plain" } });
    await expect(makeClient(fetch).images.processFromUrl("https://x/y.jpg")).rejects.toMatchObject({
      message: "something broke",
    });
  });
});

describe("retry policy", () => {
  it("retries 5xx then succeeds", async () => {
    let n = 0;
    const fetch: FetchLike = async () => {
      n++;
      if (n < 3) return new Response("", { status: 503 });
      return new Response(JSON.stringify({ id: "j", status: "Completed" }), { status: 200, headers: { "content-type": "application/json" } });
    };
    const raid = makeClient(fetch, { maxRetries: 3 });
    const job = await raid.video.getJob("j");
    expect(n).toBe(3);
    expect((job as { status: string }).status).toBe("Completed");
  });

  it("does not retry a 400", async () => {
    let n = 0;
    const fetch: FetchLike = async () => {
      n++;
      return new Response(JSON.stringify({ error: { code: "X", message: "bad" } }), { status: 400, headers: { "content-type": "application/json" } });
    };
    await expect(makeClient(fetch, { maxRetries: 3 }).video.getJob("j")).rejects.toBeInstanceOf(RaidApiError);
    expect(n).toBe(1);
  });
});

describe("multipart requests", () => {
  it("sends imageFiles + input.ExternalId as FormData", async () => {
    const { fetch, calls } = jsonFetch(200, { images: [], totalCreditsUsed: 0, totalProcessingTimeMs: 0, isSuccessful: true, hasDetailedReport: false });
    const raid = makeClient(fetch);
    await raid.images.process({ data: new Uint8Array([1, 2, 3]), fileName: "p.jpg", contentType: "image/jpeg" }, { externalId: "corr-1" });
    const init = calls[0]?.init;
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
    const form = init?.body as FormData;
    expect(form.get("input.ExternalId")).toBe("corr-1");
    expect(form.get("imageFiles")).toBeInstanceOf(Blob);
  });
});

describe("async poll helpers", () => {
  it("submitAndWait polls until a terminal status", async () => {
    const statuses = ["Queued", "Processing", "Completed"];
    let i = 0;
    const fetch: FetchLike = async (url, init) => {
      if (init?.method === "POST") {
        return new Response(JSON.stringify({ jobId: "vid-1", creditsReserved: 4 }), { status: 200, headers: { "content-type": "application/json" } });
      }
      const status = statuses[Math.min(i++, statuses.length - 1)];
      return new Response(JSON.stringify({ id: "vid-1", fileName: "c.mp4", status, progress: 100, creditsReserved: 4, creditsUsed: 4, processingTimeMs: 1, createdAt: "2026-01-01T00:00:00Z" }), { status: 200, headers: { "content-type": "application/json" } });
    };
    const raid = makeClient(fetch);
    const job = await raid.video.submitAndWait(
      { data: new Uint8Array([0]), fileName: "c.mp4" },
      { clientDurationSeconds: 10, intervalMs: 1, timeoutMs: 5_000 },
    );
    expect(job.status).toBe("Completed");
  });

  it("submitAndWait throws RaidTimeoutError when it never finishes", async () => {
    const fetch: FetchLike = async (url, init) => {
      if (init?.method === "POST") {
        return new Response(JSON.stringify({ jobId: "vid-2", creditsReserved: 4 }), { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify({ id: "vid-2", fileName: "c.mp4", status: "Processing", progress: 10, creditsReserved: 4, creditsUsed: 0, processingTimeMs: 1, createdAt: "2026-01-01T00:00:00Z" }), { status: 200, headers: { "content-type": "application/json" } });
    };
    const raid = makeClient(fetch);
    await expect(
      raid.video.submitAndWait({ data: new Uint8Array([0]), fileName: "c.mp4" }, { intervalMs: 1, timeoutMs: 5 }),
    ).rejects.toBeInstanceOf(RaidTimeoutError);
  });
});

describe("paged lists", () => {
  it("normalizes a bare array into { items, totalCount }", async () => {
    const { fetch } = jsonFetch(200, [{ id: "a" }, { id: "b" }]);
    const page = await makeClient(fetch).video.listJobs({ take: 2 });
    expect(page.totalCount).toBe(2);
    expect(page.items).toHaveLength(2);
  });

  it("normalizes a { items, totalCount } envelope", async () => {
    const { fetch } = jsonFetch(200, { items: [{ id: "a" }], totalCount: 17 });
    const page = await makeClient(fetch).factChecking.listJobs();
    expect(page.totalCount).toBe(17);
    expect(page.items).toHaveLength(1);
  });
});

// Silence unused import in environments that tree-shake aggressively.
void vi;

describe("image batch mode", () => {
  it("posts every file under imageFiles and returns the batch id", async () => {
    const { fetch, calls } = jsonFetch(202, {
      batchId: "b1", status: "Accepted", itemCount: 2,
      creditsCharged: 32, creditsPerItem: 16, realtimeCreditsPerItem: 20,
    });
    const client = makeClient(fetch);

    const res = await client.images.submitBatch(
      [
        { data: new Uint8Array([1]), fileName: "a.jpg" },
        { data: new Uint8Array([2]), fileName: "b.jpg" },
      ],
      { externalId: "job-7" },
    );

    expect(res.batchId).toBe("b1");
    expect(calls[0]?.url).toBe(`${TEST_BASE_URL}/api/app/image-forensics/batches`);

    const form = calls[0]?.init?.body as FormData;
    expect(form.getAll("imageFiles")).toHaveLength(2);
    expect(form.get("input.ExternalId")).toBe("job-7");
  });

  it("rejects an empty batch before making a request", async () => {
    const { fetch, calls } = jsonFetch(202, {});
    const client = makeClient(fetch);

    await expect(client.images.submitBatch([])).rejects.toThrow(/at least one image/);
    // The point of the guard: no credits, no round trip.
    expect(calls).toHaveLength(0);
  });

  it("polls on isTerminal rather than a status allow-list", async () => {
    // A status the SDK has never heard of must still terminate the loop when the server says so.
    const responses = [
      { batchId: "b1", status: "Accepted", isTerminal: false },
      { batchId: "b1", status: "SomeFutureStatus", isTerminal: true },
    ];
    let call = 0;
    const fetch = async (url: string) => {
      const body = url.includes("/batches/")
        ? responses[Math.min(call++, responses.length - 1)]
        : { batchId: "b1", status: "Accepted", itemCount: 1 };
      return new Response(JSON.stringify(body), {
        status: 200, headers: { "content-type": "application/json" },
      });
    };

    const client = makeClient(fetch);
    const batch = await client.images.submitBatchAndWait(
      [{ data: new Uint8Array([1]), fileName: "a.jpg" }],
      { intervalMs: 1 },
    );

    expect(batch.isTerminal).toBe(true);
    expect(batch.status).toBe("SomeFutureStatus");
  });

  it("encodes the batch id into every path", async () => {
    const { fetch, calls } = jsonFetch(200, { cancelledItems: 3, creditsRefunded: 48 });
    const client = makeClient(fetch);

    await client.images.cancelBatch("a/b?c");

    expect(calls[0]?.url).toContain("/batches/a%2Fb%3Fc/cancel");
  });
});

describe("document analysis", () => {
  /** Minimal record; the fields the resource actually branches on are `id` + `status`. */
  function analysis(status: string, extra: Record<string, unknown> = {}) {
    return {
      id: "doc-1",
      docId: "t-abc-u123",
      mediaKind: "pdf",
      docType: "",
      status,
      forensicsStatus: status,
      pagesStatus: status,
      fusedVerdict: status === "completed" ? "reject" : "",
      fusedProbability: 0,
      fusionRationale: "",
      pagesTotal: 1,
      pagesCompleted: status === "completed" ? 1 : 0,
      pagesFailed: 0,
      creditsUsed: 1,
      pages: [],
      ...extra,
    };
  }

  it("uploads the file as `file` and passes docType through", async () => {
    const { fetch, calls } = jsonFetch(202, analysis("processing"));
    const raid = makeClient(fetch);

    const res = await raid.documents.analyze(
      { data: new Uint8Array([1, 2]), fileName: "statement.pdf", contentType: "application/pdf" },
      { docType: "bank_statement" },
    );

    expect(calls[0]?.url).toBe(`${TEST_BASE_URL}/api/app/document-analysis/analyze`);
    const form = calls[0]?.init?.body as FormData;
    expect(form.get("file")).toBeInstanceOf(Blob);
    expect(form.get("docType")).toBe("bank_statement");
    // A 202 is the expected outcome, not an error — it must resolve with the partial record.
    expect(res.status).toBe("processing");
    expect(res.id).toBe("doc-1");
  });

  it("analyzeAndWait polls GET {id} until the analysis is terminal", async () => {
    const statuses = ["processing", "processing", "completed"];
    let i = 0;
    const urls: string[] = [];
    const fetch: FetchLike = async (url, init) => {
      urls.push(url);
      const body =
        init?.method === "POST"
          ? analysis("processing")
          : analysis(statuses[Math.min(i++, statuses.length - 1)]!);
      return new Response(JSON.stringify(body), {
        status: init?.method === "POST" ? 202 : 200,
        headers: { "content-type": "application/json" },
      });
    };

    const done = await makeClient(fetch).documents.analyzeAndWait(
      { data: new Uint8Array([0]), fileName: "a.pdf" },
      { intervalMs: 1, timeoutMs: 5_000 },
    );

    expect(done.status).toBe("completed");
    expect(urls[1]).toBe(`${TEST_BASE_URL}/api/app/document-analysis/doc-1`);
  });

  it("analyzeAndWait returns immediately when the upload already came back terminal", async () => {
    const { fetch, calls } = jsonFetch(200, analysis("completed"));
    const done = await makeClient(fetch).documents.analyzeAndWait(
      { data: new Uint8Array([0]), fileName: "a.pdf" },
      { intervalMs: 1 },
    );
    expect(done.status).toBe("completed");
    // No wasted poll — the upload response was already final.
    expect(calls).toHaveLength(1);
  });

  it("analyzeAndWait times out without hanging on a stuck analysis", async () => {
    const { fetch } = jsonFetch(202, analysis("processing"));
    await expect(
      makeClient(fetch).documents.analyzeAndWait(
        { data: new Uint8Array([0]), fileName: "a.pdf" },
        { intervalMs: 1, timeoutMs: 5 },
      ),
    ).rejects.toBeInstanceOf(RaidTimeoutError);
  });

  it("returns page rasters as bytes, not parsed JSON", async () => {
    const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47]);
    const calls: string[] = [];
    const fetch: FetchLike = async (url) => {
      calls.push(url);
      return new Response(png, { status: 200, headers: { "content-type": "image/png" } });
    };

    const image = await makeClient(fetch).documents.pageImage("doc-1", 2);

    expect(calls[0]).toBe(`${TEST_BASE_URL}/api/app/document-analysis/doc-1/pages/2/image`);
    expect(image.contentType).toBe("image/png");
    expect(Array.from(image.data)).toEqual(Array.from(png));
  });

  it("maps a JSON error body on a binary endpoint to RaidApiError", async () => {
    const { fetch } = jsonFetch(404, { error: { code: "NOT_FOUND", message: "Page not found." } });
    await expect(makeClient(fetch).documents.pageImage("doc-1", 9)).rejects.toMatchObject({
      status: 404,
      code: "NOT_FOUND",
    });
  });

  it("sends the evidence lane / page / redaction as query params", async () => {
    const calls: string[] = [];
    const fetch: FetchLike = async (url) => {
      calls.push(url);
      return new Response(new Uint8Array([1]), {
        status: 200,
        headers: { "content-type": "image/png" },
      });
    };

    await makeClient(fetch).documents.evidence("doc-1", {
      feature: "tampering",
      page: 2,
      redaction: "redaction-p2-a.png",
    });

    expect(calls[0]).toContain("feature=tampering");
    expect(calls[0]).toContain("page=2");
    expect(calls[0]).toContain("redaction=redaction-p2-a.png");
  });

  it("reads credit info from the server rather than assuming the defaults", async () => {
    const { fetch, calls } = jsonFetch(200, {
      currentBalance: 12,
      creditCostPerDocument: 1,
      maxBatchFiles: 5,
      analyzeConcurrency: 3,
      maxFileSizeMB: 40,
      maxImageSizeMB: 10,
      userHeadroomRemaining: null,
      canUseFeature: true,
    });

    const info = await makeClient(fetch).documents.creditInfo();

    expect(calls[0]?.url).toBe(`${TEST_BASE_URL}/api/app/document-analysis/credit-info`);
    expect(info.maxFileSizeMB).toBe(40);
    expect(info.userHeadroomRemaining).toBeNull();
  });

  it("encodes the analysis id into every path", async () => {
    const { fetch, calls } = jsonFetch(200, analysis("completed"));
    await makeClient(fetch).documents.get("a/b?c");
    expect(calls[0]?.url).toContain("/document-analysis/a%2Fb%3Fc");
  });
});

describe("audio", () => {
  // A realistic detection response as the platform serves it: `workflowType` is the workflow's
  // NAME on the wire (the request takes the number), and `metadata` carries the detector's detail.
  const VOICE_OK = {
    isSuccessful: true,
    errorMessage: null,
    workflowType: "AiDetectionOnly",
    isAiDetected: true,
    detectionConfidence: 0.93,
    detectionClassification: "fake",
    processingTimeMs: 2110,
    creditsUsed: 1,
    metadata: {
      provider: "raid_1b",
      detection_method: "raid_1b_llr_global_mean",
      score: 0.994,
      score_basis: "percentile_vs_genuine",
      p_fake: 0.31,
      probability_calibrated: false,
      threshold_calibrated: true,
      threshold_global_tau: -4.93,
      threshold_partial_tau: -3.03,
      threshold_fired_global: true,
      low_confidence: false,
      chunks: [{ index: 0, chunk: "0-4s", result: "fake", confidence: 0.91, score: 0.29, start_s: 0, end_s: 4, llr: -7.1 }],
      settings: { hop_s: 2.0 },
    },
  };

  it("process sends audioFile + input.WorkflowType as FormData", async () => {
    const { fetch, calls } = jsonFetch(200, VOICE_OK);
    const raid = makeClient(fetch);
    await raid.audio.process({ data: new Uint8Array([1, 2, 3]), fileName: "a.mp3", contentType: "audio/mpeg" }, { workflowType: 4 });
    expect(calls[0]?.url).toBe(`${TEST_BASE_URL}/api/app/voice-analysis/process`);
    const form = calls[0]?.init?.body as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect(form.get("audioFile")).toBeInstanceOf(Blob);
    expect(form.get("input.WorkflowType")).toBe("4");
  });

  it("types the detection details on metadata and keeps unknown keys reachable", async () => {
    const { fetch } = jsonFetch(200, VOICE_OK);
    const res = await makeClient(fetch).audio.process({ data: new Uint8Array([1]), fileName: "a.wav", contentType: "audio/wav" });
    expect(res.workflowType).toBe("AiDetectionOnly");
    expect(res.metadata?.provider).toBe("raid_1b");
    expect(res.metadata?.score).toBe(0.994);
    expect(res.metadata?.score_basis).toBe("percentile_vs_genuine");
    expect(res.metadata?.probability_calibrated).toBe(false);
    expect(res.metadata?.threshold_partial_tau).toBe(-3.03);
    expect(res.metadata?.chunks?.[0]?.llr).toBe(-7.1);
    // Keys the spec leaves untyped still ride through.
    expect((res.metadata as Record<string, unknown> | null | undefined)?.settings).toEqual({ hop_s: 2.0 });
  });

  it("processFromUrl posts JSON and omits unset options", async () => {
    const { fetch, calls } = jsonFetch(200, VOICE_OK);
    await makeClient(fetch).audio.processFromUrl("https://example.com/a.mp3");
    expect(calls[0]?.url).toBe(`${TEST_BASE_URL}/api/app/voice-analysis/process-from-url`);
    expect(JSON.parse(calls[0]?.init?.body as string)).toEqual({ url: "https://example.com/a.mp3" });
  });
});

describe("credits and limits", () => {
  it("reads each modality's own credit-info route", async () => {
    // The shapes differ (per image / per frame / per workflow), so there is no shared endpoint.
    const { fetch, calls } = jsonFetch(200, {
      currentBalance: 480,
      tenantCredits: 480,
      creditCostPerImage: 1,
      creditCostPerFrame: 1,
      maxFileSizeMB: 50,
      allowedFileFormats: "jpg,png",
      canUseFeature: true,
    });
    const raid = makeClient(fetch);

    expect((await raid.images.creditInfo()).creditCostPerImage).toBe(1);
    expect((await raid.audio.creditInfo()).tenantCredits).toBe(480);
    expect((await raid.video.creditInfo()).creditCostPerFrame).toBe(1);
    expect((await raid.factChecking.creditInfo()).currentBalance).toBe(480);

    expect(calls.map((c) => c.url)).toEqual([
      `${TEST_BASE_URL}/api/app/image-forensics/credit-info`,
      `${TEST_BASE_URL}/api/app/voice-analysis/credit-info`,
      `${TEST_BASE_URL}/api/app/video-forensics/credit-info`,
      `${TEST_BASE_URL}/api/app/fact-checking/credit-info`,
    ]);
  });
});
