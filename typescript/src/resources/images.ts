import type { RaidClient } from "../client.js";
import type {
  ImageBatch,
  ImageBatchCancelResult,
  ImageBatchPage,
  ImageBatchResultPage,
  ImageBatchSubmitResponse,
  ImageForensicsCreditInfo,
  ImageForensicsResponse,
} from "../types.js";
import { pollUntil, type PollOptions } from "../poll.js";
import { appendFile, type FileInput } from "../upload.js";

export interface ImageProcessOptions {
  /** Caller-provided ID to correlate this analysis with your own systems. */
  externalId?: string;
  /** Source URL of the image, recorded for your own auditing. */
  sourceUrl?: string;
}

export interface ImageProcessFromUrlOptions {
  externalId?: string;
}

/** Image forensics — detect AI-generated, deepfaked, and digitally edited images. Synchronous. */

/** Options for {@link Images.submitBatch}. */
export interface ImageBatchSubmitOptions {
  /** Caller-provided ID echoed back on the batch, to reconcile against your own systems. */
  externalId?: string;
}

/** Paging options for {@link Images.listBatches} and {@link Images.batchResults}. */
export interface ImageBatchListOptions {
  skip?: number;
  take?: number;
}

export class Images {
  constructor(private readonly client: RaidClient) {}

  /**
   * Analyze one or more image files (up to 10 per request). Returns a verdict,
   * confidence, and — on detailed plans — generator attribution per image.
   * Requires an API key with the `image` scope.
   */
  process(files: FileInput | FileInput[], options: ImageProcessOptions = {}): Promise<ImageForensicsResponse> {
    const list = Array.isArray(files) ? files : [files];
    if (list.length === 0) {
      throw new Error("images.process: provide at least one image file.");
    }
    const form = new FormData();
    for (const file of list) {
      appendFile(form, "imageFiles", file);
    }
    if (options.externalId !== undefined) form.append("input.ExternalId", options.externalId);
    if (options.sourceUrl !== undefined) form.append("sourceUrl", options.sourceUrl);

    return this.client.request<ImageForensicsResponse>({
      method: "POST",
      path: "/api/app/image-forensics/process",
      form,
    });
  }

  /** Analyze an image fetched from a public URL (a direct link or a page the resolver extracts from). */
  processFromUrl(url: string, options: ImageProcessFromUrlOptions = {}): Promise<ImageForensicsResponse> {
    return this.client.request<ImageForensicsResponse>({
      method: "POST",
      path: "/api/app/image-forensics/process-from-url",
      json: { url, externalId: options.externalId },
    });
  }

  /**
   * Queue images for analysis in a later scheduled window, at a reduced credit cost.
   *
   * Returns immediately with a batch ID — **no verdicts**. Credits are deducted on acceptance,
   * and refunded for any image that ultimately fails.
   *
   * Batch mode is images-only; no other modality has a batch tier.
   *
   * Two differences from {@link Images.process} are structural, not temporary:
   * - **Turnaround is up to a full processing window**, so never put this on a path where a
   *   person is waiting.
   * - **Results are basic tier** — `deepAnalysis`, `generators` and `heatmapUrl` are always null,
   *   whatever the plan. Those are realtime-only.
   */
  async submitBatch(
    files: FileInput[],
    options: ImageBatchSubmitOptions = {},
  ): Promise<ImageBatchSubmitResponse> {
    if (files.length === 0) {
      throw new Error("submitBatch requires at least one image");
    }

    const form = new FormData();
    for (const file of files) {
      appendFile(form, "imageFiles", file);
    }
    if (options.externalId) form.append("input.ExternalId", options.externalId);

    return this.client.request<ImageBatchSubmitResponse>({
      method: "POST",
      path: "/api/app/image-forensics/batches",
      form,
    });
  }

  /** Current status and counters for one batch. */
  async getBatch(batchId: string): Promise<ImageBatch> {
    return this.client.request<ImageBatch>({
      method: "GET",
      path: `/api/app/image-forensics/batches/${encodeURIComponent(batchId)}`,
    });
  }

  /** Your batches, newest first. */
  async listBatches(options: ImageBatchListOptions = {}): Promise<ImageBatchPage> {
    return this.client.request<ImageBatchPage>({
      method: "GET",
      path: "/api/app/image-forensics/batches",
      query: { skip: options.skip, take: options.take },
    });
  }

  /**
   * Per-image results.
   *
   * Individual images become available as they finish — you do not have to wait for the whole
   * batch. Match results to your inputs with `ordinal`, which is the image's position in the
   * original submission; file names are echoed back but are not guaranteed unique.
   */
  async batchResults(
    batchId: string,
    options: ImageBatchListOptions = {},
  ): Promise<ImageBatchResultPage> {
    return this.client.request<ImageBatchResultPage>({
      method: "GET",
      path: `/api/app/image-forensics/batches/${encodeURIComponent(batchId)}/results`,
      query: { skip: options.skip, take: options.take },
    });
  }

  /**
   * Cancel the images still waiting and refund their credits.
   *
   * Images already being analyzed are left to finish — they have consumed the work either way —
   * so the refund covers only what was actually cancelled.
   */
  async cancelBatch(batchId: string): Promise<ImageBatchCancelResult> {
    return this.client.request<ImageBatchCancelResult>({
      method: "POST",
      path: `/api/app/image-forensics/batches/${encodeURIComponent(batchId)}/cancel`,
      json: {},
    });
  }

  /**
   * Queue a batch and poll until it reaches a terminal state, then return it.
   *
   * **Rarely what you want.** A batch can legitimately take hours, so this holds a process open
   * for the entire window; the default poll timeout will usually expire first. Prefer
   * {@link Images.submitBatch}, persist the ID, and collect results later — that is the whole
   * point of the tier. This exists for tests and short-window setups.
   *
   * Polling stops on the server-computed `isTerminal` rather than a status allow-list, so it keeps
   * working if a status is ever added.
   */
  async submitBatchAndWait(
    files: FileInput[],
    options: ImageBatchSubmitOptions & PollOptions = {},
  ): Promise<ImageBatch> {
    const { intervalMs, timeoutMs, onPoll, ...submitOptions } = options;
    const { batchId } = await this.submitBatch(files, submitOptions);

    if (!batchId) {
      throw new Error("submitBatch did not return a batchId");
    }

    return pollUntil(
      () => this.getBatch(batchId),
      (batch) => batch.isTerminal === true,
      (batch) => batch.status ?? "unknown",
      { intervalMs, timeoutMs, onPoll },
    );
  }

  /**
   * Read the credit balance and the live image limits: cost per image, max file size and allowed
   * formats, plus whether the batch tier is available and what it costs. Read these rather than
   * hard-coding the defaults — they are account settings and can change without an SDK release.
   * Any valid API token may call this; no scope is required.
   */
  creditInfo(): Promise<ImageForensicsCreditInfo> {
    return this.client.request<ImageForensicsCreditInfo>({
      method: "GET",
      path: "/api/app/image-forensics/credit-info",
    });
  }
}
