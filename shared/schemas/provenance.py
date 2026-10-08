"""
RE:TRACE Canonical Provenance Schema.

Enforces strict 5-category data provenance model per ORIGINAL_REQUEST.md:59-65.
Never present simulated, assumed, or AI-estimated values as physical measurements.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProvenanceCategory(str, Enum):
    """
    Mandatory provenance categories for all system data points.
    """
    MEASURED = "MEASURED"                    # Verified physical scale / weighbridge reading
    OBSERVED = "OBSERVED"                    # Human / operator visual observation
    AI_ESTIMATED = "AI_ESTIMATED"            # Computer vision inference output
    REFERENCE_ASSUMED = "REFERENCE_ASSUMED"  # OEM Bill of Materials or baseline reference
    SIMULATED = "SIMULATED"                  # Synthetic test fixture or mock data


class ProvenanceRecord(BaseModel):
    """
    Canonical record attaching explicit provenance to any critical numerical measurement.
    """
    model_config = ConfigDict(frozen=True)

    value: float = Field(..., description="Numerical measured or estimated value")
    unit: str = Field(..., description="Physical measurement unit (e.g., 'kg', 'units', '%')")
    category: ProvenanceCategory = Field(..., description="Mandatory provenance category")
    source_id: str = Field(..., description="Identifier of the capturing sensor, operator, model, or benchmark")
    captured_at: datetime = Field(..., description="UTC timestamp when measurement was recorded")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score in [0.0, 1.0], mandatory for AI_ESTIMATED",
    )
    tolerance_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=50.0,
        description="Measurement tolerance/uncertainty band (+/- %)",
    )

    @model_validator(mode="after")
    def validate_confidence_for_ai_estimated(self) -> "ProvenanceRecord":
        """
        Enforces that confidence score in [0.0, 1.0] is mandatory when
        category is AI_ESTIMATED per Section R2:2 and R3:1.
        """
        if self.category == ProvenanceCategory.AI_ESTIMATED and self.confidence is None:
            raise ValueError(
                "Confidence score is mandatory for AI_ESTIMATED provenance records."
            )
        return self

