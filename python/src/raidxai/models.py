"""Clean re-exports of the generated Pydantic models.

The single source of truth is ``../spec/openapi.yaml``; ``_generated/models.py`` is
produced from it by ``datamodel-code-generator`` (see ``scripts/generate.sh``).
This module gives each schema a stable public name so callers import
``from raidxai import ImageForensicsResponse`` rather than reaching into ``_generated``.
"""

from __future__ import annotations

from ._generated.models import (
    Claim,
    DocumentAnalysis,
    DocumentAnalysisCreditInfo,
    DocumentAnalysisPage,
    DocumentAnalysisRegion,
    DocumentDataStatus,
    DocumentExtraction,
    DocumentExtractionFieldCheck,
    DocumentExtractionFieldOverride,
    DocumentExtractionPage,
    DocumentExtractionSkipReason,
    DocumentExtractionStatus,
    DocumentFeatureScore,
    DocumentFinding,
    DocumentFusedVerdict,
    DocumentMediaKind,
    DocumentPageAiStatus,
    DocumentPageAiVerdict,
    DocumentPageVerdict,
    DocumentRefundReason,
    DocumentStatus,
    DocumentType,
    DocumentVerdict,
    Error,
    FactCheckingCreditInfo,
    FactCheckJob,
    FactCheckResult,
    Generators,
    ImageBatch,
    ImageBatchCancelResult,
    ImageBatchItemStatus,
    ImageBatchPage,
    ImageBatchResult,
    ImageBatchResultPage,
    ImageBatchStatus,
    ImageBatchSubmitResponse,
    ImageFace,
    ImageFaceAnalysis,
    ImageForensicsCreditInfo,
    ImageForensicsResponse,
    ImageResult,
    JobStatus,
    JobSubmitResponse,
    Modality,
    ProvenanceItem,
    ProvenanceUrl,
    Verdict,
    VideoForensicsCreditInfo,
    VideoJob,
    VideoResult,
    VideoSubmitResponse,
    VoiceAnalysisCreditInfo,
    VoiceAnalysisResponse,
    VoiceDetectionChunk,
    VoiceDetectionDetails,
    VoiceWorkflowType,
)

#: Document-analysis statuses that will never change again — polling stops here.
#:
#: Note ``fused_verdict`` is only meaningful once the analysis is ``completed``: it is empty
#: while processing, and a ``failed`` analysis reports ``insufficient_quality``.
TERMINAL_DOCUMENT_STATUSES = frozenset({DocumentStatus.completed, DocumentStatus.failed})

# Terminal states for the async modalities (video + fact-checking).
TERMINAL_JOB_STATUSES = frozenset({JobStatus.completed, JobStatus.failed, JobStatus.cancelled})

#: Batch statuses that will never change again.
#:
#: Prefer ``batch.is_terminal`` where you have the object — it is server-computed, so it keeps
#: working if a status is ever added. This set is for callers holding only a status value.
TERMINAL_BATCH_STATUSES = frozenset(
    {
        ImageBatchStatus.completed,
        ImageBatchStatus.completed_with_errors,
        ImageBatchStatus.cancelled,
        ImageBatchStatus.failed,
    }
)

__all__ = [
    "Claim",
    "DocumentAnalysis",
    "DocumentAnalysisCreditInfo",
    "DocumentAnalysisPage",
    "DocumentAnalysisRegion",
    "DocumentDataStatus",
    "DocumentExtraction",
    "DocumentExtractionFieldCheck",
    "DocumentExtractionFieldOverride",
    "DocumentExtractionPage",
    "DocumentExtractionSkipReason",
    "DocumentExtractionStatus",
    "DocumentFeatureScore",
    "DocumentFinding",
    "DocumentFusedVerdict",
    "DocumentMediaKind",
    "DocumentPageAiStatus",
    "DocumentPageAiVerdict",
    "DocumentPageVerdict",
    "DocumentRefundReason",
    "DocumentStatus",
    "DocumentType",
    "DocumentVerdict",
    "TERMINAL_DOCUMENT_STATUSES",
    "Error",
    "FactCheckJob",
    "FactCheckResult",
    "Generators",
    "ImageBatch",
    "ImageBatchCancelResult",
    "ImageBatchItemStatus",
    "ImageBatchPage",
    "ImageBatchResult",
    "ImageBatchResultPage",
    "ImageBatchStatus",
    "ImageBatchSubmitResponse",
    "TERMINAL_BATCH_STATUSES",
    "ImageFace",
    "ImageFaceAnalysis",
    "ImageForensicsResponse",
    "ImageResult",
    "JobStatus",
    "JobSubmitResponse",
    "Modality",
    "ProvenanceItem",
    "ProvenanceUrl",
    "Verdict",
    "VideoJob",
    "VideoResult",
    "VideoSubmitResponse",
    "VoiceAnalysisResponse",
    "VoiceDetectionChunk",
    "VoiceDetectionDetails",
    "VoiceWorkflowType",
    "TERMINAL_JOB_STATUSES",
    "FactCheckingCreditInfo",
    "ImageForensicsCreditInfo",
    "VideoForensicsCreditInfo",
    "VoiceAnalysisCreditInfo",
]
