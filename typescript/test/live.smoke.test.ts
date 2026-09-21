import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { describe, it, expect } from "vitest";
import { RaidClient } from "../src/index.js";

/**
 * Live smoke test against a real Raid AI tier. Skipped unless RAID_API_KEY and
 * RAID_API_BASE_URL are set, so it never breaks CI. To run it:
 *
 *   RAID_API_KEY=<your-api-key> \
 *   RAID_API_BASE_URL=<raid-ai-api-url> \
 *   npm test
 *
 * Uses a tiny 1×1 PNG so it exercises the real multipart + auth + response path
 * without needing a fixture file.
 */
const apiKey = process.env.RAID_API_KEY;
const baseUrl = process.env.RAID_API_BASE_URL;
// Opt-in: path to a short speech clip. Audio detection costs credits, so it never runs by default.
const audioPath = process.env.RAID_SMOKE_AUDIO_PATH;

// A 1×1 transparent PNG.
const ONE_PX_PNG = Uint8Array.from(
  atob(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  ),
  (c) => c.charCodeAt(0),
);

describe.skipIf(!(apiKey && baseUrl))("live smoke", () => {
  // Constructed lazily — the describe body runs even when the suite is skipped.
  const raid = apiKey && baseUrl ? new RaidClient({ apiKey, baseUrl }) : null;

  it("images.process returns a verdict", async () => {
    const res = await raid!.images.process({ data: ONE_PX_PNG, fileName: "smoke.png", contentType: "image/png" });
    expect(res).toHaveProperty("images");
    expect(Array.isArray(res.images)).toBe(true);
  }, 120_000);

  it.skipIf(!audioPath)("audio.process returns a named workflow and typed detection details", async () => {
    const res = await raid!.audio.process({ data: readFileSync(audioPath!), fileName: basename(audioPath!) });
    expect(typeof res.workflowType).toBe("string");
    if (res.isSuccessful && res.metadata) {
      if (res.metadata.provider !== undefined) expect(typeof res.metadata.provider).toBe("string");
      if (res.metadata.score !== undefined) {
        expect(res.metadata.score).toBeGreaterThanOrEqual(0);
        expect(res.metadata.score).toBeLessThanOrEqual(1);
      }
    }
  }, 300_000);
});
