"""
backend/app/api/v1/ai.py — Dual-Mode AI Observation Service API Endpoints.
Enforces Section R3: AI is strictly observation/estimation, NEVER verification decision.
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status
from ml.models.vision_schemas import AIObservationResult
from ml.inference.dual_mode_observer import DualModeAIObservationService
from backend.app.services.storage_service import storage_service
from backend.app.core.errors import ResourceNotFoundError
from backend.app.core.config import settings

router = APIRouter(prefix="/ai", tags=["AI Observation"])

ai_service = DualModeAIObservationService(
    default_mode=settings.ai_mode,
)


class ObserveRequest(BaseModel):
    file_id: str = Field(..., description="Uploaded physical evidence file ID")
    product_id: Optional[str] = Field(None, description="Optional associated product ID")
    force_mode: Optional[str] = Field(None, description="'LIVE_GEMINI' or 'DETERMINISTIC_FIXTURE'")
    fixture_override: Optional[str] = Field(None, description="Override fixture name for deterministic replay")
    allow_fallback: bool = Field(True, description="Allow fallback to deterministic fixture on Gemini error")


@router.post("/observe", response_model=AIObservationResult)
def observe_evidence(req: ObserveRequest):
    """
    Executes computer vision observation over physical evidence.
    Dual-mode: Live Gemini Multimodal API with graceful fallback to deterministic fixture.
    Strictly tags output as AI_ESTIMATED.
    """
    record = storage_service.get_record(req.file_id)
    if not record:
        raise ResourceNotFoundError(f"Evidence file '{req.file_id}' not found.")

    content = storage_service.get_content(req.file_id)
    if content is None:
        raise ResourceNotFoundError(f"Evidence file '{req.file_id}' content missing from disk.")

    result = ai_service.observe(
        file_bytes=content,
        filename=record.filename,
        mime_type=record.mime_type,
        product_id=req.product_id,
        force_mode=req.force_mode,
        fixture_override=req.fixture_override,
        evidence_id=record.file_id,
        evidence_sha256=record.sha256_hash,
        allow_fallback=req.allow_fallback,
    )
    return result
