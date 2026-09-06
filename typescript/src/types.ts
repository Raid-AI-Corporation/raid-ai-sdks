/**
 * Friendly, hand-curated aliases over the generated OpenAPI schema types.
 *
 * The single source of truth is `../spec/openapi.yaml`; `src/generated/openapi.ts`
 * is produced from it by `npm run generate:types` (openapi-typescript). This module
 * re-exports each schema under a clean name so consumers import
 * `ImageForensicsResponse` rather than `components["schemas"]["ImageForensicsResponse"]`.
 *
 * Regenerate + review this file's exports whenever the spec changes.
 */

import type { components } from "./generated/openapi.js";

type Schemas = components["schemas"];

// ── Shared enums / primitives ────────────────────────────────────────────────
export type Verdict = Schemas["Verdict"];
export type JobStatus = Schemas["JobStatus"];
export type Modality = Schemas["Modality"];
export type VoiceWorkflowType = Schemas["VoiceWorkflowType"];
export type Generators = Schemas["Generators"];
/** The `{ error: { code, message } }` envelope every endpoint returns on failure. */
export type ErrorEnvelope = Schemas["Error"];

// ── Image ────────────────────────────────────────────────────────────────────
export type ImageResult = Schemas["ImageResult"];
export type ImageForensicsResponse = Schemas["ImageForensicsResponse"];
export type ImageFaceAnalysis = Schemas["ImageFaceAnalysis"];
export type ImageFace = Schemas["ImageFace"];

// ── Image batch mode (images only — no other modality has a batch tier) ──────
export type ImageProcessingMode = "REALTIME" | "BATCH";
export type ImageBatchStatus = Schemas["ImageBatchStatus"];
export type ImageBatchItemStatus = Schemas["ImageBatchItemStatus"];
export type ImageBatchSubmitResponse = Schemas["ImageBatchSubmitResponse"];
export type ImageBatch = Schemas["ImageBatch"];
export type ImageBatchPage = Schemas["ImageBatchPage"];
export type ImageBatchResult = Schemas["ImageBatchResult"];
export type ImageBatchResultPage = Schemas["ImageBatchResultPage"];
export type ImageBatchCancelResult = Schemas["ImageBatchCancelResult"];

/**
 * Batch statuses that will never change again.
 *
 * Prefer `batch.isTerminal` where you have the object — it is server-computed, so it keeps
 * working if a status is ever added. This list exists for callers that only have a status string.
 */
export const TERMINAL_BATCH_STATUSES = [
  "Completed",
  "CompletedWithErrors",
  "Cancelled",
  "Failed",
] as const satisfies readonly ImageBatchStatus[];

// ── Audio ────────────────────────────────────────────────────────────────────
export type VoiceAnalysisResponse = Schemas["VoiceAnalysisResponse"];
/** Detector detail on `VoiceAnalysisResponse.metadata` for the detection workflow. Every field is optional. */
export type VoiceDetectionDetails = Schemas["VoiceDetectionDetails"];
/** One analysis window of the audio timeline (`VoiceDetectionDetails.chunks[]`). */
export type VoiceDetectionChunk = Schemas["VoiceDetectionChunk"];

// ── Async submit responses ────────────────────────────────────────────────────
export type VideoSubmitResponse = Schemas["VideoSubmitResponse"];
export type JobSubmitResponse = Schemas["JobSubmitResponse"];

// ── Video ─────────────────────────────────────────────────────────────────────
export type VideoResult = Schemas["VideoResult"];
export type VideoJob = Schemas["VideoJob"];

// ── Credits & limits (one per modality — each has its own pricing shape) ─────
export type ImageForensicsCreditInfo = Schemas["ImageForensicsCreditInfo"];
export type VoiceAnalysisCreditInfo = Schemas["VoiceAnalysisCreditInfo"];
export type VideoForensicsCreditInfo = Schemas["VideoForensicsCreditInfo"];
export type FactCheckingCreditInfo = Schemas["FactCheckingCreditInfo"];

// ── Document ─────────────────────────────────────────────────────────────────
export type DocumentType = Schemas["DocumentType"];
export type DocumentStatus = Schemas["DocumentStatus"];
export type DocumentMediaKind = Schemas["DocumentMediaKind"];
export type DocumentFusedVerdict = Schemas["DocumentFusedVerdict"];
export type DocumentRefundReason = Schemas["DocumentRefundReason"];
export type DocumentPageVerdict = Schemas["DocumentPageVerdict"];
export type DocumentPageAiStatus = Schemas["DocumentPageAiStatus"];
export type DocumentPageAiVerdict = Schemas["DocumentPageAiVerdict"];
export type DocumentFinding = Schemas["DocumentFinding"];
export type DocumentFeatureScore = Schemas["DocumentFeatureScore"];
export type DocumentVerdict = Schemas["DocumentVerdict"];
export type DocumentAnalysisRegion = Schemas["DocumentAnalysisRegion"];
export type DocumentAnalysisPage = Schemas["DocumentAnalysisPage"];
export type DocumentAnalysis = Schemas["DocumentAnalysis"];
export type DocumentAnalysisCreditInfo = Schemas["DocumentAnalysisCreditInfo"];

/**
 * Analysis statuses that will never change again — polling stops here.
 *
 * Note `fusedVerdict` is only meaningful once the analysis is `completed`: it is empty
 * while processing, and a `failed` analysis reports `insufficient_quality`.
 */
export const TERMINAL_DOCUMENT_STATUSES = [
  "completed",
  "failed",
] as const satisfies readonly DocumentStatus[];

/**
 * A raw-bytes response — the document page rasters and evidence crops.
 *
 * `data` is a copy of the body, so it is safe to keep after the request resolves.
 */
export interface BinaryResponse {
  data: Uint8Array;
  /** The response's `Content-Type`, e.g. `image/png`. */
  contentType: string;
}

// ── Fact-checking ──────────────────────────────────────────────────────────────
export type ProvenanceUrl = Schemas["ProvenanceUrl"];
export type ProvenanceItem = Schemas["ProvenanceItem"];
export type Claim = Schemas["Claim"];
export type FactCheckResult = Schemas["FactCheckResult"];
export type FactCheckJob = Schemas["FactCheckJob"];

/**
 * A page of `?skip=&take=` list results. The list endpoints return a raw array in
 * some deployments and a `{ items, totalCount }` envelope in others — the resource
 * methods normalize to this shape.
 */
export interface PagedResult<T> {
  items: T[];
  totalCount: number;
}

/** Terminal job states — polling stops when a job reaches one of these. */
export const TERMINAL_JOB_STATUSES: readonly JobStatus[] = ["Completed", "Failed", "Cancelled"];
