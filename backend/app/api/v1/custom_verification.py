"""
backend/app/api/v1/custom_verification.py — Custom Recycling Verification API Endpoint.

Exposes the generic verification pipeline through a user-facing Custom Verification workflow.
Composes existing:
- Passport lookup and lifecycle state checks
- Recycling event ingestion
- Physical evidence references
- Optional AI observation
- Deterministic mass-balance evaluation
- RFC 8785 evidence bundle compilation & hashing
- Local EVM blockchain anchoring
- Proof-of-Recycling (PoR) certificate generation
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, status

from shared.schemas.provenance import ProvenanceCategory
from shared.schemas.evidence_bundle import (
    EvidenceBundle,
    MassBalanceVerificationResult,
)
from shared.schemas.por_certificate import ProofOfRecyclingCertificate
from ml.models.vision_schemas import AIObservationResult
from backend.app.services.custom_verification_service import custom_verification_service

router = APIRouter(prefix="/custom-verification", tags=["Custom Verification"])


class CustomClaimedMaterial(BaseModel):
    material_name: str = Field(..., min_length=1, description="Name of claimed recovered material (e.g. 'Cobalt', 'Nickel')")
    claimed_mass_kg: float = Field(..., ge=0.0, description="Recovered secondary mass claimed in kg")
    purity_pct: float = Field(default=95.0, ge=0.0, le=100.0, description="Assayed or declared chemical purity %")
    provenance: ProvenanceCategory = Field(
        default=ProvenanceCategory.OBSERVED,
        description="Data provenance category (defaults to OBSERVED for user-entered data)"
    )


class CustomVerificationRequest(BaseModel):
    passport_id: str = Field(..., min_length=1, description="Target Digital Product Passport identifier")
    facility_id: str = Field(default="FAC-CUSTOM-01", min_length=1, description="Authorized recycling facility license ID")
    operator_id: str = Field(default="OP-CUSTOM-01", min_length=1, description="Operating technician identifier")
    intake_gross_mass_kg: float = Field(..., gt=0.0, description="Physical gross intake mass in kg")
    intake_mass_provenance: ProvenanceCategory = Field(
        default=ProvenanceCategory.OBSERVED,
        description="Provenance of intake scale reading (defaults to OBSERVED)"
    )
    processing_method: str = Field(
        default="HYDROMETALLURGICAL",
        min_length=1,
        description="Recycling metallurgical/mechanical route"
    )
    claimed_materials: List[CustomClaimedMaterial] = Field(
        ..., min_length=1, description="Declared recovered secondary materials output"
    )
    evidence_file_ids: List[str] = Field(
        ..., min_length=1, description="List of uploaded physical evidence file IDs (from /evidence/upload)"
    )
    event_id: Optional[str] = Field(
        None, description="Optional unique recycling event ID (auto-generated if omitted)"
    )
    run_ai_observation: bool = Field(
        default=False, description="Whether to execute AI observation over uploaded evidence"
    )
    ai_file_id: Optional[str] = Field(
        None, description="Specific evidence file ID to observe (defaults to first evidence file)"
    )
    ai_force_mode: Optional[str] = Field(
        None, description="Optional AI execution mode: 'LIVE_GEMINI' or 'DETERMINISTIC_FIXTURE'"
    )
    ai_fixture_override: Optional[str] = Field(
        None, description="Optional deterministic fixture override"
    )
    scale_uncertainty_pct: float = Field(
        default=0.5, ge=0.0, le=5.0, description="Scale calibration tolerance percentage"
    )


class BlockchainAnchorInfo(BaseModel):
    network_label: str
    chain_id: int
    is_anchored: bool
    tx_hash: Optional[str] = None
    evidence_commitment: str
    block_number: Optional[int] = None


class CustomVerificationResponse(BaseModel):
    event_id: str
    passport_id: str
    overall_decision: str  # "VERIFIED", "REVIEW", "FLAGGED", "EVIDENCE_INTEGRITY_FAILURE"
    mass_balance_decision: str  # "VALID", "BORDERLINE", "IMPOSSIBLE"
    evidence_integrity_status: str  # "VERIFIED" or "BREACHED"
    evidence_integrity_message: str
    lifecycle_state: str
    mathematical_explanation: str
    mass_balance_result: MassBalanceVerificationResult
    evidence_bundle: EvidenceBundle
    blockchain: BlockchainAnchorInfo
    certificate: Optional[ProofOfRecyclingCertificate] = None
    certificate_block_reason: Optional[str] = None
    ai_observation: Optional[AIObservationResult] = None
    ai_notice: Optional[str] = None


@router.post(
    "/verify",
    response_model=CustomVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Custom Recycling Verification"
)
def verify_custom_recycling(req: CustomVerificationRequest):
    """
    Executes an end-to-end custom recycling verification workflow:
    1. Validates passport eligibility in RECYCLING_PENDING.
    2. Validates physical mass claims and evidence file references.
    3. Runs optional AI visual observation (observes evidence; never makes verification decision).
    4. Deterministically evaluates mass balance (closed-form thermodynamic conservation).
    5. Compiles RFC 8785 canonical evidence bundle and computes keccak256 commitment.
    6. Verifies evidence integrity against on-disk content.
    7. Anchors commitment to local EVM blockchain and advances lifecycle state.
    8. Issues Proof-of-Recycling certificate when legitimately verified.
    """
    raw_claims = [c.model_dump(mode="python") for c in req.claimed_materials]

    result = custom_verification_service.process_custom_verification(
        passport_id=req.passport_id,
        facility_id=req.facility_id,
        operator_id=req.operator_id,
        intake_gross_mass_kg=req.intake_gross_mass_kg,
        claimed_materials_data=raw_claims,
        evidence_file_ids=req.evidence_file_ids,
        intake_mass_provenance=req.intake_mass_provenance,
        processing_method=req.processing_method,
        event_id=req.event_id,
        run_ai_observation=req.run_ai_observation,
        ai_file_id=req.ai_file_id,
        ai_force_mode=req.ai_force_mode,
        ai_fixture_override=req.ai_fixture_override,
        scale_uncertainty_pct=req.scale_uncertainty_pct,
    )

    return CustomVerificationResponse(**result)
