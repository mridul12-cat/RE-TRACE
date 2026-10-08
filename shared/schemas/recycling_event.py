"""
RE:TRACE Canonical Recycling Event Schema.

Captures facility intake events, gross mass readings, recovery claims,
evidence references, and enforces unique event_id anti-replay semantics.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field

from shared.schemas.provenance import ProvenanceCategory


class ClaimedMaterial(BaseModel):
    """
    Individual material output claimed by a recycling facility.
    """
    material_name: str = Field(..., description="Name of claimed recovered material (e.g., 'Cobalt', 'Nickel')")
    claimed_mass_kg: float = Field(..., ge=0.0, description="Mass claimed to be recovered from this batch in kg")
    purity_pct: float = Field(default=95.0, ge=0.0, le=100.0, description="Assayed or declared chemical purity %")
    provenance: ProvenanceCategory = Field(
        default=ProvenanceCategory.MEASURED,
        description="Provenance of the recovery measurement (MEASURED or OBSERVED)",
    )


class RecyclingEvent(BaseModel):
    """
    Canonical recycling intake and claim submission event.
    """
    event_id: str = Field(..., description="Globally unique UUID for the recycling event to prevent replay attacks")
    passport_id: str = Field(..., description="Target Digital Product Passport identifier")
    facility_id: str = Field(..., description="Authorized recycling facility identifier or license ID")
    operator_id: str = Field(..., description="Authorized human operator or station identifier")
    intake_gross_mass_kg: float = Field(..., gt=0.0, description="Physical gross intake mass on facility weighbridge")
    intake_mass_provenance: ProvenanceCategory = Field(
        default=ProvenanceCategory.MEASURED,
        description="Mandatory provenance for intake scale reading",
    )
    claimed_materials: List[ClaimedMaterial] = Field(
        ...,
        min_length=1,
        description="Declared recovered materials output from batch",
    )
    evidence_file_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of file IDs for uploaded physical evidence (photos, weight tickets, video stills)",
    )
    processing_method: str = Field(
        default="HYDROMETALLURGICAL",
        description="Recycling metallurgical/mechanical route (e.g., 'HYDROMETALLURGICAL', 'PYROMETALLURGICAL')",
    )
    timestamp: datetime = Field(..., description="UTC timestamp of intake/processing")
    status: str = Field(
        default="SUBMITTED",
        description="Current workflow status ('SUBMITTED', 'VERIFIED', 'FLAGGED', 'BORDERLINE_REVIEW')",
    )
