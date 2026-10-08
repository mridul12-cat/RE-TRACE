"""
ml/models/vision_schemas.py — Computer Vision & Multimodal Observation Schemas.
Conforms strictly to ADR-001 and shared.schemas.provenance.
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from shared.schemas.provenance import ProvenanceCategory


class BoundingBox(BaseModel):
    ymin: float = Field(..., ge=0.0, le=1.0)
    xmin: float = Field(..., ge=0.0, le=1.0)
    ymax: float = Field(..., ge=0.0, le=1.0)
    xmax: float = Field(..., ge=0.0, le=1.0)


class DetectedItem(BaseModel):
    label: str = Field(..., description="Detected component label (e.g., 'EV_BATTERY_MODULE_6S2P')")
    count: int = Field(..., ge=1, description="Estimated count of detected units")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Visual detection confidence score")
    bounding_box: Optional[BoundingBox] = None


class AIObservationResult(BaseModel):
    """
    Standardized observation output from the Dual-Mode AI Observation Service.
    Strictly marked AI_ESTIMATED per ADR-001 trust boundaries.
    """
    provider: str = Field(..., description="AI Service provider ('google-gemini' or 'deterministic-replay')")
    model: str = Field(..., description="Model identifier (e.g. 'gemini-2.5-flash' or 'fixture-v1.0')")
    execution_mode: str = Field(..., description="'LIVE_GEMINI' or 'DETERMINISTIC_FIXTURE'")
    inference_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when inference completed"
    )
    detected_items: List[DetectedItem] = Field(
        default_factory=list,
        description="List of physical items visually classified"
    )
    material_estimates: Dict[str, float] = Field(
        default_factory=dict,
        description="Estimated element masses in kg (Cobalt, Nickel, etc.)"
    )
    estimated_item_count: int = Field(
        default=0,
        description="Total detected unit count"
    )
    estimated_gross_mass_kg: float = Field(
        default=0.0,
        description="Visual volumetric mass estimate in kg"
    )
    confidence: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Aggregate confidence score"
    )
    anomaly_flags: List[str] = Field(
        default_factory=list,
        description="Observed physical anomalies (e.g. 'CASING_BREACH', 'NON_STANDARD_PACKAGING')"
    )
    provenance_category: ProvenanceCategory = Field(
        default=ProvenanceCategory.AI_ESTIMATED,
        description="Strict provenance attribution: AI_ESTIMATED"
    )
    notes: Optional[str] = None
