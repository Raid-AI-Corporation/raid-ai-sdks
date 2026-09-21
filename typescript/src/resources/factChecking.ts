import type { RaidClient } from "../client.js";
import type {
  FactCheckJob,
  FactCheckingCreditInfo,
  JobSubmitResponse,
  Modality,
  PagedResult,
} from "../types.js";
import { TERMINAL_JOB_STATUSES } from "../types.js";
import { appendFile, type FileInput } from "../upload.js";
import { pollUntil, type PollOptions } from "../poll.js";
import { normalizePaged } from "./paging.js";

export interface FactCheckSubmitOptions {
  /** Free-text context to guide the check. Echoed back on the job. */
  userContext?: string;
}

export interface FactCheckSubmitFromUrlOptions {
  userContext?: string;
}

export interface FactCheckListOptions {
  skip?: number;
  take?: number;
}

/** Fact-checking — check images, audio, and video against the public record. Asynchronous: submit, then poll. */
export class FactChecking {
  constructor(private readonly client: RaidClient) {}

  /** Submit a media file to fact-check. Returns a `jobId` to poll. Requires the `fact-check` scope. */
  submit(file: FileInput, modality: Modality, options: FactCheckSubmitOptions = {}): Promise<JobSubmitResponse> {
    const form = new FormData();
    appendFile(form, "file", file);
    form.append("modality", modality);
    if (options.userContext !== undefined) form.append("userContext", options.userContext);

    return this.client.request<JobSubmitResponse>({
      method: "POST",
      path: "/api/app/fact-checking/submit",
      form,
    });
  }

  /** Submit media from a public URL to fact-check. Returns a `jobId` to poll. */
  submitFromUrl(
    url: string,
    modality: Modality,
    options: FactCheckSubmitFromUrlOptions = {},
  ): Promise<JobSubmitResponse> {
    return this.client.request<JobSubmitResponse>({
      method: "POST",
      path: "/api/app/fact-checking/submit-from-url",
      json: { url, modality, userContext: options.userContext },
    });
  }

  /** Fetch the current state of a fact-checking job. `result` is populated once `status` is `Completed`. */
  getJob(jobId: string): Promise<FactCheckJob> {
    return this.client.request<FactCheckJob>({
      method: "GET",
      path: `/api/app/fact-checking/jobs/${encodeURIComponent(jobId)}`,
    });
  }

  /** List submitted fact-checking jobs, most recent first. */
  async listJobs(options: FactCheckListOptions = {}): Promise<PagedResult<FactCheckJob>> {
    const raw = await this.client.request<unknown>({
      method: "GET",
      path: "/api/app/fact-checking/jobs",
      query: { skip: options.skip, take: options.take },
    });
    return normalizePaged<FactCheckJob>(raw);
  }

  /** Cancel a running fact-checking job. */
  cancel(jobId: string): Promise<void> {
    return this.client.request<void>({
      method: "POST",
      path: `/api/app/fact-checking/jobs/${encodeURIComponent(jobId)}/cancel`,
    });
  }

  /**
   * Submit a fact-check and poll until the job reaches a terminal state
   * (`Completed` / `Failed` / `Cancelled`). Convenience over `submit` + `getJob`.
   */
  async submitAndWait(
    file: FileInput,
    modality: Modality,
    options: FactCheckSubmitOptions & PollOptions = {},
  ): Promise<FactCheckJob> {
    const { intervalMs, timeoutMs, onPoll, ...submitOptions } = options;
    const { jobId } = await this.submit(file, modality, submitOptions);
    return pollUntil<FactCheckJob>(
      () => this.getJob(jobId),
      (job) => TERMINAL_JOB_STATUSES.includes(job.status),
      (job) => job.status,
      { intervalMs, timeoutMs, onPoll: onPoll as PollOptions["onPoll"] },
    );
  }

  /**
   * Read the credit balance and the live fact-checking limits: the cost per modality, the per-job
   * credit cap, max file size and allowed formats. Read these rather than hard-coding the
   * defaults — they are account settings and can change without an SDK release. Any valid API
   * token may call this; no scope is required.
   */
  creditInfo(): Promise<FactCheckingCreditInfo> {
    return this.client.request<FactCheckingCreditInfo>({
      method: "GET",
      path: "/api/app/fact-checking/credit-info",
    });
  }
}
