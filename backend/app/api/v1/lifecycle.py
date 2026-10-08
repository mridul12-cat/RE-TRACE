"""
backend/app/api/v1/lifecycle.py — Lifecycle State Transition & Quarantine Endpoints.
Enforces ADR-001 Pillar 2: 7-state finite state machine & role-based transition guards.
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from shared.domain.lifecycle import LifecycleState, AuthorizedRole
from backend.app.services.blockchain_service import blockchain_service

router = APIRouter(prefix="/lifecycle", tags=["Lifecycle"])


class TransitionRequest(BaseModel):
    passport_id: str = Field(..., description="Digital Product Passport identifier")
    target_state: LifecycleState = Field(..., description="Target lifecycle state")
    actor_role: AuthorizedRole = Field(..., description="Actor role initiating transition")
    has_auditor_notes: bool = Field(False, description="Whether auditor justification is supplied")


class FlagRequest(BaseModel):
    passport_id: str = Field(..., description="Passport ID to quarantine")
    reason: str = Field(..., description="Reason for flagging")
    event_id: Optional[str] = None


class ResolveFlagRequest(BaseModel):
    passport_id: str = Field(..., description="Quarantined passport ID")
    auditor_address: str = Field(..., description="Authorized auditor wallet address")
    target_state: LifecycleState = Field(
        default=LifecycleState.RECYCLING_VERIFIED,
        description="Target resolved state"
    )
    notes: str = Field(..., min_length=5, description="Documented auditor resolution notes")


@router.post("/transition")
def transition_lifecycle_state(req: TransitionRequest):
    """
    Executes a product lifecycle transition.
    Enforces role authorization, linear state progression, and anti-replay guards (Adversarial Case G).
    """
    tx_hash = blockchain_service.transition_state(
        passport_id=req.passport_id,
        target_state=req.target_state,
        actor_role=req.actor_role,
        has_auditor_notes=req.has_auditor_notes
    )
    return {
        "success": True,
        "passport_id": req.passport_id,
        "target_state": req.target_state.value,
        "tx_hash": tx_hash,
    }


@router.post("/flag")
def flag_product(req: FlagRequest):
    """Quarantines a product into FLAGGED state upon anomaly or fraud detection."""
    blockchain_service.flag_product(
        passport_id=req.passport_id,
        reason=req.reason,
        event_id=req.event_id
    )
    return {
        "success": True,
        "passport_id": req.passport_id,
        "state": LifecycleState.FLAGGED.value,
        "reason": req.reason,
    }


@router.post("/resolve-flag")
def resolve_flag(req: ResolveFlagRequest):
    """
    Resolves a quarantined product from FLAGGED state.
    Strictly restricted to AUDITOR role with documented notes (ADR-001 Pillar 2).
    """
    blockchain_service.resolve_flag(
        passport_id=req.passport_id,
        auditor_address=req.auditor_address,
        target_state=req.target_state,
        notes=req.notes
    )
    return {
        "success": True,
        "passport_id": req.passport_id,
        "state": req.target_state.value,
        "resolved_by": req.auditor_address,
        "notes": req.notes,
    }


@router.get("/state/{passport_id}")
def get_current_state(passport_id: str):
    """Returns the current on-chain lifecycle state for a passport."""
    state = blockchain_service.get_lifecycle_state(passport_id)
    return {
        "passport_id": passport_id,
        "lifecycle_state": state.value,
    }
