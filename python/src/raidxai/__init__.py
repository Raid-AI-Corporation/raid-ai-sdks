"""Official Python SDK for the Raid AI detection API.

Detect AI-generated and manipulated media (images, audio, video), analyze documents
for tampering and AI generation, and fact-check media against the public record.

    from raidxai import RaidClient, FileInput

    raid = RaidClient(api_key="<your-api-key>")
    res = raid.images.process(FileInput.from_path("photo.jpg"))
    print(res.images[0].verdict)

Full reference: https://docs.raidxai.com
"""

from __future__ import annotations

from ._core import BinaryResponse
from ._specs import PagedResult
from .aio import AsyncRaidClient
from .client import RaidClient
from .errors import RaidApiError, RaidTimeoutError
from .files import FileInput
from .models import (
    Claim,
    DocumentAnalysis,
    DocumentAnalysisCreditInfo,
    DocumentAnalysisPage,
    DocumentAnalysisRegion,
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
    FactCheckingCreditInfo,
    FactCheckJob,
    FactCheckResult,
    Generators,
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
from .resources.audio import VoiceWorkflow

__version__ = "0.2.0"

__all__ = [
    "RaidClient",
    "AsyncRaidClient",
    "BinaryResponse",
    "FileInput",
    "PagedResult",
    "RaidApiError",
    "RaidTimeoutError",
    "VoiceWorkflow",
    # models
    "Claim",
    "DocumentAnalysis",
    "DocumentAnalysisCreditInfo",
    "DocumentAnalysisPage",
    "DocumentAnalysisRegion",
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
    "FactCheckJob",
    "FactCheckResult",
    "Generators",
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
    "__version__",
    "FactCheckingCreditInfo",
    "ImageForensicsCreditInfo",
    "VideoForensicsCreditInfo",
    "VoiceAnalysisCreditInfo",
]
