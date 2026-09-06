import type { RaidClient } from "../client.js";
import type {
  BinaryResponse,
  DocumentAnalysis,
  DocumentAnalysisCreditInfo,
  DocumentType,
} from "../types.js";
import { TERMINAL_DOCUMENT_STATUSES } from "../types.js";
import { appendFile, type FileInput } from "../upload.js";
import { pollUntil, type PollOptions } from "../poll.js";

export interface DocumentAnalyzeOptions {
  /**
   * Hint for the kind of document. Optional — the pipeline classifies the document itself
   * when this is omitted, and an unrecognized value is ignored rather than rejected.
   */
  docType?: DocumentType;
}

export interface DocumentEvidenceOptions {
  /** Which feature lane's evidence to read. */
  feature: "tampering" | "consistency" | "anomaly";
  /** 1-based page number. */
  page?: number;
  /**
   * Read a recovered-redaction crop instead of the page raster — the `redaction-p{page}-….png`
   * name as it appears in the lane's `evidenceUris`.
   */
  redaction?: string;
}

/**
 * A full analysis runs for minutes, so the poll budget is far longer than the other
 * modalities' 5 minutes. Raise it with `timeoutMs` for long documents.
 */
const DEFAULT_ANALYZE_TIMEOUT_MS = 900_000;

/** True once an analysis will not change again. */
function isTerminal(analysis: DocumentAnalysis): boolean {
  return (TERMINAL_DOCUMENT_STATUSES as readonly string[]).includes(analysis.status);
}

/**
 * Document analysis — one upload returns both a document-level forensics verdict and
 * per-page tampering / AI-generation results.
 *
 * Asynchronous: `analyze` uploads and returns the record, then you poll `get` (or let
 * `analyzeAndWait` do it) until `status` is `completed` or `failed`.
 */
export class Documents {
  constructor(private readonly client: RaidClient) {}

  /**
   * Upload a PDF or image for analysis. Requires the `document-image` scope.
   *
   * Returns the analysis record whether the server finished inside its wait budget or
   * not — the shape is identical either way, so check `status` (usually `processing`)
   * and poll {@link get} with `id`. Never re-upload to "retry" a still-running
   * analysis: the record is already there, and a second upload is a second charge.
   */
  analyze(file: FileInput, options: DocumentAnalyzeOptions = {}): Promise<DocumentAnalysis> {
    const form = new FormData();
    appendFile(form, "file", file);
    if (options.docType !== undefined) form.append("docType", options.docType);

    return this.client.request<DocumentAnalysis>({
      method: "POST",
      path: "/api/app/document-analysis/analyze",
      form,
    });
  }

  /** Fetch one analysis. `pages` grows and `verdict` fills in as the analysis progresses. */
  get(id: string): Promise<DocumentAnalysis> {
    return this.client.request<DocumentAnalysis>({
      method: "GET",
      path: `/api/app/document-analysis/${encodeURIComponent(id)}`,
    });
  }

  /**
   * Upload a document and poll until the analysis is `completed` or `failed`.
   * Convenience over `analyze` + `get`; the poll budget defaults to 15 minutes.
   */
  async analyzeAndWait(
    file: FileInput,
    options: DocumentAnalyzeOptions & PollOptions = {},
  ): Promise<DocumentAnalysis> {
    const { intervalMs, timeoutMs, onPoll, ...analyzeOptions } = options;
    const submitted = await this.analyze(file, analyzeOptions);
    // The upload may already have come back terminal — don't spend a poll to learn that.
    if (isTerminal(submitted)) {
      onPoll?.(submitted);
      return submitted;
    }
    return pollUntil<DocumentAnalysis>(
      () => this.get(submitted.id),
      isTerminal,
      (analysis) => analysis.status,
      {
        intervalMs,
        timeoutMs: timeoutMs ?? DEFAULT_ANALYZE_TIMEOUT_MS,
        onPoll: onPoll as PollOptions["onPoll"],
      },
    );
  }

  /**
   * Fetch the rendered raster for one page (`image/png`) — the exact pixels a page's
   * `editedRegions` coordinates are measured against, so region boxes can be drawn on it
   * directly. Available while the page's `hasImage` is true.
   */
  pageImage(id: string, pageNumber: number): Promise<BinaryResponse> {
    return this.client.request<BinaryResponse>({
      method: "GET",
      path: `/api/app/document-analysis/${encodeURIComponent(id)}/pages/${pageNumber}/image`,
      binary: true,
    });
  }

  /**
   * Fetch one forensics evidence raster for a feature lane and page. The storage URI is
   * resolved server-side from this analysis's own verdict — you address a crop by lane and
   * page, never by URI.
   */
  evidence(id: string, options: DocumentEvidenceOptions): Promise<BinaryResponse> {
    return this.client.request<BinaryResponse>({
      method: "GET",
      path: `/api/app/document-analysis/${encodeURIComponent(id)}/evidence`,
      query: { feature: options.feature, page: options.page, redaction: options.redaction },
      binary: true,
    });
  }

  /**
   * Read the live credit balance and upload constraints (size ceilings, batch limits,
   * request concurrency). Call it before a batch instead of hard-coding the defaults —
   * they are server-side settings and can change without an SDK release.
   */
  creditInfo(): Promise<DocumentAnalysisCreditInfo> {
    return this.client.request<DocumentAnalysisCreditInfo>({
      method: "GET",
      path: "/api/app/document-analysis/credit-info",
    });
  }
}
