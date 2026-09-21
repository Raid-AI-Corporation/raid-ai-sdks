import type { RaidClient } from "../client.js";
import type {
  PagedResult,
  VideoForensicsCreditInfo,
  VideoJob,
  VideoSubmitResponse,
} from "../types.js";
import { TERMINAL_JOB_STATUSES } from "../types.js";
import { appendFile, type FileInput } from "../upload.js";
import { pollUntil, type PollOptions } from "../poll.js";
import { normalizePaged } from "./paging.js";

export interface VideoSubmitOptions {
  /**
   * Video duration in seconds, read from the file by your client. Strongly recommended
   * so credits are reserved accurately at submit time.
   */
  clientDurationSeconds?: number;
  /** Source URL of the video, for your own auditing. */
  sourceUrl?: string;
}

export interface VideoSubmitFromUrlOptions {
  clientDurationSeconds?: number;
}

export interface VideoListOptions {
  skip?: number;
  take?: number;
}

/** Video forensics — detect deepfake / AI-generated video. Asynchronous: submit, then poll. */
export class Video {
  constructor(private readonly client: RaidClient) {}

  /** Submit a video file for analysis. Returns a `jobId` to poll. Requires the `video` scope. */
  submit(file: FileInput, options: VideoSubmitOptions = {}): Promise<VideoSubmitResponse> {
    const form = new FormData();
    appendFile(form, "file", file);
    if (options.clientDurationSeconds !== undefined) {
      form.append("clientDurationSeconds", String(options.clientDurationSeconds));
    }
    if (options.sourceUrl !== undefined) form.append("sourceUrl", options.sourceUrl);

    return this.client.request<VideoSubmitResponse>({
      method: "POST",
      path: "/api/app/video-forensics/submit",
      form,
    });
  }

  /** Submit a video fetched from a public URL. Returns a `jobId` to poll. */
  submitFromUrl(url: string, options: VideoSubmitFromUrlOptions = {}): Promise<VideoSubmitResponse> {
    return this.client.request<VideoSubmitResponse>({
      method: "POST",
      path: "/api/app/video-forensics/submit-from-url",
      json: { url, clientDurationSeconds: options.clientDurationSeconds },
    });
  }

  /** Fetch the current state of a video job. `result` is populated once `status` is `Completed`. */
  getJob(jobId: string): Promise<VideoJob> {
    return this.client.request<VideoJob>({
      method: "GET",
      path: `/api/app/video-forensics/jobs/${encodeURIComponent(jobId)}`,
    });
  }

  /** List submitted video jobs, most recent first. */
  async listJobs(options: VideoListOptions = {}): Promise<PagedResult<VideoJob>> {
    const raw = await this.client.request<unknown>({
      method: "GET",
      path: "/api/app/video-forensics/jobs",
      query: { skip: options.skip, take: options.take },
    });
    return normalizePaged<VideoJob>(raw);
  }

  /** Cancel a running video job. */
  cancel(jobId: string): Promise<void> {
    return this.client.request<void>({
      method: "POST",
      path: `/api/app/video-forensics/jobs/${encodeURIComponent(jobId)}/cancel`,
    });
  }

  /**
   * Submit a video and poll until the job reaches a terminal state
   * (`Completed` / `Failed` / `Cancelled`). Convenience over `submit` + `getJob`.
   */
  async submitAndWait(
    file: FileInput,
    options: VideoSubmitOptions & PollOptions = {},
  ): Promise<VideoJob> {
    const { intervalMs, timeoutMs, onPoll, ...submitOptions } = options;
    const { jobId } = await this.submit(file, submitOptions);
    return pollUntil<VideoJob>(
      () => this.getJob(jobId),
      (job) => TERMINAL_JOB_STATUSES.includes(job.status),
      (job) => job.status,
      { intervalMs, timeoutMs, onPoll: onPoll as PollOptions["onPoll"] },
    );
  }

  /**
   * Read the credit balance and the live video limits: cost per frame, frames analyzed per
   * second, the longest video allowed and what it costs, max file size, allowed formats, and
   * today's usage against the daily cap. Read these rather than hard-coding the defaults — they
   * are account settings and can change without an SDK release. Any valid API token may call
   * this; no scope is required.
   */
  creditInfo(): Promise<VideoForensicsCreditInfo> {
    return this.client.request<VideoForensicsCreditInfo>({
      method: "GET",
      path: "/api/app/video-forensics/credit-info",
    });
  }
}
