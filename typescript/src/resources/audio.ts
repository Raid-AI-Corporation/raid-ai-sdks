import type { RaidClient } from "../client.js";
import type {
  VoiceAnalysisCreditInfo,
  VoiceAnalysisResponse,
  VoiceWorkflowType,
} from "../types.js";
import { appendFile, type FileInput } from "../upload.js";

/** Voice workflow selector — mirrors `VoiceWorkflowType` in the API. */
export const VoiceWorkflow = {
  TranscriptionOnly: 1,
  IntelligenceOnly: 2,
  Combined: 3,
  /** Default — detect whether a voice is AI-generated or cloned. */
  AiDetectionOnly: 4,
} as const satisfies Record<string, VoiceWorkflowType>;

export interface AudioProcessOptions {
  /** Which workflow to run (default `4` — AI-voice detection). */
  workflowType?: VoiceWorkflowType;
  /** Text to analyze for the Intelligence / Combined workflows (max 50,000 chars). */
  textInput?: string;
  /** Context to guide analysis (max 500 chars). */
  contextHints?: string;
  /** Source URL of the audio, recorded for your own auditing. */
  sourceUrl?: string;
}

export interface AudioProcessFromUrlOptions {
  workflowType?: VoiceWorkflowType;
  textInput?: string;
  contextHints?: string;
}

/**
 * Voice analysis — detect AI-generated / cloned voices, with optional transcription + intelligence.
 * Synchronous.
 *
 * `detectionConfidence` on the response is confidence in the verdict that was reported, measured
 * as distance past the decision boundary — NOT the probability that the audio is AI-generated.
 * `0.5` means the clip landed on the boundary itself, and the opposite verdict's confidence is not
 * `1 - detectionConfidence`.
 *
 * `metadata` is typed as `VoiceDetectionDetails` for the detection workflow. Which detector runs
 * is chosen per account by the Raid AI platform — there is no selector on the request — and every
 * field in it is optional. The number to show a user is `metadata.score` (a percentile against the
 * detector's own genuine speech, valid when `score_basis` says so); `metadata.p_fake` is a raw
 * ranking, not a probability, and must not be shown as a percentage. `metadata.provider` names the
 * detector that produced the verdict, as an open string.
 */
export class Audio {
  constructor(private readonly client: RaidClient) {}

  /** Analyze an audio file. Requires an API key with the `audio` scope. */
  process(file: FileInput, options: AudioProcessOptions = {}): Promise<VoiceAnalysisResponse> {
    const form = new FormData();
    appendFile(form, "audioFile", file);
    if (options.workflowType !== undefined) form.append("input.WorkflowType", String(options.workflowType));
    if (options.textInput !== undefined) form.append("input.TextInput", options.textInput);
    if (options.contextHints !== undefined) form.append("input.ContextHints", options.contextHints);
    if (options.sourceUrl !== undefined) form.append("sourceUrl", options.sourceUrl);

    return this.client.request<VoiceAnalysisResponse>({
      method: "POST",
      path: "/api/app/voice-analysis/process",
      form,
    });
  }

  /** Analyze audio fetched from a public URL (a direct audio link or a video/social page whose audio is extracted). */
  processFromUrl(url: string, options: AudioProcessFromUrlOptions = {}): Promise<VoiceAnalysisResponse> {
    return this.client.request<VoiceAnalysisResponse>({
      method: "POST",
      path: "/api/app/voice-analysis/process-from-url",
      json: {
        url,
        workflowType: options.workflowType,
        textInput: options.textInput,
        contextHints: options.contextHints,
      },
    });
  }

  /**
   * Read the credit balance and the live audio limits: what each workflow costs, which ones the
   * balance currently covers, max file size, allowed formats and the batch limit. Read these
   * rather than hard-coding the defaults — they are account settings and can change without an
   * SDK release. Any valid API token may call this; no scope is required.
   */
  creditInfo(): Promise<VoiceAnalysisCreditInfo> {
    return this.client.request<VoiceAnalysisCreditInfo>({
      method: "GET",
      path: "/api/app/voice-analysis/credit-info",
    });
  }
}
