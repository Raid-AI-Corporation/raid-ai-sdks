import { describe, it, expect } from "vitest";
import { RaidClient, RaidTimeoutError, type FetchLike } from "../src/index.js";

function makeClient(fetch: FetchLike, overrides = {}) {
  return new RaidClient({ apiKey: "test-key", baseUrl: "https://api.example.test", fetch, maxRetries: 0, ...overrides });
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("poll uses the full timeout budget", () => {
  it("catches a job that completes on the last poll before the deadline", async () => {
    const statuses = ["Processing", "Processing", "Completed"];
    let i = 0;
    const fetch: FetchLike = async (_url, init) => {
      if (init?.method === "POST") return json(200, { jobId: "job-1", creditsReserved: 1 });
      const status = statuses[Math.min(i++, statuses.length - 1)];
      return json(200, {
        id: "job-1", fileName: "c.mp4", status, progress: 100,
        creditsReserved: 1, creditsUsed: 1, processingTimeMs: 1, createdAt: "2026-01-01T00:00:00Z",
      });
    };
    // interval 15ms, timeout 40ms → the old `now + interval >= deadline` guard would
    // throw before the 3rd poll; the fixed loop polls to completion.
    const job = await makeClient(fetch).video.submitAndWait(
      { data: new Uint8Array([0]), fileName: "c.mp4" },
      { intervalMs: 15, timeoutMs: 40 },
    );
    expect(job.status).toBe("Completed");
  });

  it("still throws RaidTimeoutError when the job never finishes", async () => {
    const fetch: FetchLike = async (_url, init) => {
      if (init?.method === "POST") return json(200, { jobId: "job-2", creditsReserved: 1 });
      return json(200, {
        id: "job-2", fileName: "c.mp4", status: "Processing", progress: 1,
        creditsReserved: 1, creditsUsed: 0, processingTimeMs: 1, createdAt: "2026-01-01T00:00:00Z",
      });
    };
    await expect(
      makeClient(fetch).video.submitAndWait({ data: new Uint8Array([0]), fileName: "c.mp4" }, { intervalMs: 5, timeoutMs: 20 }),
    ).rejects.toBeInstanceOf(RaidTimeoutError);
  });
});

describe("timeout covers the body read", () => {
  it("aborts (does not hang) when the body never resolves", async () => {
    // A fetch whose body read never settles until aborted — the client's timeout
    // must abort it. Before the fix, the abort timer was cleared once headers arrived.
    const fetch: FetchLike = async (_url, init) => {
      const signal = init?.signal;
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new Uint8Array([123])); // "{" — starts JSON, never completes
          signal?.addEventListener("abort", () => controller.error(new Error("aborted")));
        },
      });
      return new Response(body, { status: 200, headers: { "content-type": "application/json" } });
    };
    await expect(
      makeClient(fetch, { timeoutMs: 30 }).video.getJob("j"),
    ).rejects.toThrow(); // resolves (rejects) rather than hanging forever
  }, 2000);
});
