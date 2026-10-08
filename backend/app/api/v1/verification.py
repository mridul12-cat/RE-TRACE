"""
backend/app/api/v1/verification.py — Deterministic Mass-Balance & Integrity Verification API.
Implements Sections R3, R4, and Adversarial Cases A, B, C, D.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from shared.domain.mass_balance import evaluate_mass_balance, MassBalanceOutcome
from shared.domain.lifecycle import LifecycleState, AuthorizedRole
from shared.schemas.evidence_bundle import (
    EvidenceBundle,
    AIInferenceObservation,
    MassBalanceVerificationResult,
)
from backend.app.services.mass_balance_service import mass_balance_service
from backend.app.services.evidence_service import evidence_service
from backend.app.services.blockchain_service import blockchain_service
from backend.app.api.v1.recycling import get_event_by_id
from backend.app.api.v1.passports import _PASSPORT_STORE
from backend.app.core.errors import (
    ResourceNotFoundError,
    EvidenceIntegrityError,
)

router = APIRouter(prefix="/verification", tags=["Verification"])


class VerificationEvaluationRequest(BaseModel):
    event_id: str = Field(..., description="Recycling event to evaluate")
    scale_uncertainty_pct: float = Field(0.5, ge=0.0, le=5.0, description="Scale tolerance percentage")
    ai_observation: Optional[AIInferenceObservation] = None


class VerificationEvaluationResponse(BaseModel):
    event_id: str
    passport_id: str
    decision: str
    lifecycle_state: str
    mathematical_explanation: str
    mass_balance_result: MassBalanceVerificationResult
    evidence_bundle: EvidenceBundle
    onchain_tx_hash: Optional[str] = None
    is_anchored: bool


class VerifyEvidenceRequest(BaseModel):
    event_id: str = Field(..., description="Recycling event ID to verify")


@router.post("/evaluate", response_model=VerificationEvaluationResponse)
def evaluate_recycling_event(req: VerificationEvaluationRequest):
    """
    Executes deterministic mass-balance verification over an ingested recycling event.
    Three possible outcomes:
    - VALID: Anchors commitment on-chain; transitions to RECYCLING_VERIFIED.
    - BORDERLINE: Retains RECYCLING_PENDING; flags for supervisor assay review.
    - IMPOSSIBLE: Quarantines batch; transitions to FLAGGED.
    """
    event = get_event_by_id(req.event_id)
    if not event:
        raise ResourceNotFoundError(f"Recycling event '{req.event_id}' not found.")

    passport = _PASSPORT_STORE.get(event.passport_id)
    if not passport:
        raise ResourceNotFoundError(f"Passport '{event.passport_id}' not found.")

    # 1. Deterministic Mass-Balance Evaluation (Closed-Form Physics)
    mb_result = mass_balance_service.evaluate(
        intake_mass_kg=event.intake_gross_mass_kg,
        composition=passport.material_composition,
        claimed_materials=event.claimed_materials,
        scale_uncertainty_pct=req.scale_uncertainty_pct
    )

    # 2. Compile Evidence Bundle & Cryptographic Commitment (RFC 8785)
    bundle = evidence_service.compile_bundle(
        event_id=event.event_id,
        passport_id=passport.passport_id,
        evidence_file_ids=event.evidence_file_ids,
        ai_observation=req.ai_observation,
        mass_balance_result=mb_result
    )

    onchain_tx = None
    is_anchored = False

    # 3. State Machine & Blockchain Anchoring Decisions
    dec_str = mb_result.decision.value if hasattr(mb_result.decision, "value") else str(mb_result.decision)
    if dec_str == "VALID":
        # Anchor on-chain
        onchain_tx = blockchain_service.anchor_evidence(
            event_id=event.event_id,
            passport_id=passport.passport_id,
            evidence_commitment=bundle.bundle_keccak256_commitment
        )
        is_anchored = True
        # Transition lifecycle state to RECYCLING_VERIFIED
        blockchain_service.transition_state(
            passport_id=passport.passport_id,
            target_state=LifecycleState.RECYCLING_VERIFIED,
            actor_role=AuthorizedRole.VERIFIER_SERVICE
        )
        current_state = LifecycleState.RECYCLING_VERIFIED.value

    elif dec_str == "BORDERLINE":
        # Keep in RECYCLING_PENDING; require supervisor review
        current_state = blockchain_service.get_lifecycle_state(passport.passport_id).value

    else:  # IMPOSSIBLE
        # Quarantine product: transition to FLAGGED
        blockchain_service.flag_product(
            passport_id=passport.passport_id,
            reason=f"Mass balance violation: {mb_result.mathematical_explanation[:200]}",
            event_id=event.event_id
        )
        current_state = LifecycleState.FLAGGED.value

    return VerificationEvaluationResponse(
        event_id=event.event_id,
        passport_id=passport.passport_id,
        decision=dec_str,
        lifecycle_state=current_state,
        mathematical_explanation=mb_result.mathematical_explanation,
        mass_balance_result=mb_result,
        evidence_bundle=bundle,
        onchain_tx_hash=onchain_tx,
        is_anchored=is_anchored
    )


@router.post("/verify-evidence")
def verify_evidence_integrity(req: VerifyEvidenceRequest):
    """
    Recomputes physical evidence digests and canonical manifest commitments.
    Verifies match against anchored blockchain commitment (Adversarial Case D).
    """
    bundle = evidence_service.get_bundle(req.event_id)
    if not bundle:
        raise ResourceNotFoundError(f"Evidence bundle for event '{req.event_id}' not found.")

    onchain_event = blockchain_service.get_event(req.event_id)
    expected_commitment = onchain_event.evidence_commitment if onchain_event else None

    is_valid, msg = evidence_service.verify_bundle_integrity(
        bundle=bundle,
        expected_onchain_commitment=expected_commitment
    )

    if not is_valid:
        raise EvidenceIntegrityError(msg)

    return {
        "is_valid": True,
        "event_id": req.event_id,
        "bundle_id": bundle.bundle_id,
        "canonical_manifest_sha256": bundle.canonical_manifest_sha256,
        "bundle_keccak256_commitment": bundle.bundle_keccak256_commitment,
        "message": msg
    }
