"""
backend/app/api/v1/certificates.py — Proof-of-Recycling (PoR) Certificate Endpoints.
Enforces Section R5: Anti-Replay on certificates and independent verification.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from shared.schemas.por_certificate import (
    ProofOfRecyclingCertificate,
    VerifiedMaterialQuantity,
)
from backend.app.services.certificate_service import certificate_service
from backend.app.services.blockchain_service import blockchain_service
from backend.app.api.v1.recycling import get_event_by_id
from backend.app.core.errors import (
    ResourceNotFoundError,
    DuplicateCertificateError,
    IllegalTransitionError,
)

router = APIRouter(prefix="/certificates", tags=["Certificates"])


class IssueCertificateRequest(BaseModel):
    event_id: str = Field(..., description="Anchored recycling event ID")
    facility_id: str = Field(..., description="Recycling facility license ID")
    verified_materials: List[VerifiedMaterialQuantity] = Field(
        ..., min_length=1, description="Verified recovered secondary materials"
    )
    verification_confidence: float = Field(0.96, ge=0.0, le=1.0)


@router.post("/issue", response_model=ProofOfRecyclingCertificate, status_code=status.HTTP_201_CREATED)
def issue_certificate(req: IssueCertificateRequest):
    """
    Issues an immutable Proof-of-Recycling certificate.
    Enforces that product is in RECYCLING_VERIFIED state and evidence is anchored.
    Rejects duplicate certificates for the same event (Adversarial Case F).
    """
    event = get_event_by_id(req.event_id)
    if not event:
        raise ResourceNotFoundError(f"Recycling event '{req.event_id}' not found.")

    onchain_event = blockchain_service.get_event(req.event_id)
    if not onchain_event:
        raise IllegalTransitionError(
            f"Event '{req.event_id}' is not anchored on-chain. Cannot issue certificate."
        )

    cert = certificate_service.generate_and_issue_certificate(
        passport_id=event.passport_id,
        event_id=event.event_id,
        facility_id=req.facility_id,
        verified_materials=req.verified_materials,
        evidence_commitment=onchain_event.evidence_commitment,
        verification_confidence=req.verification_confidence
    )
    return cert


@router.get("/{certificate_id}", response_model=ProofOfRecyclingCertificate)
def get_certificate(certificate_id: str):
    """Retrieves an issued Proof-of-Recycling certificate."""
    cert = certificate_service.get_certificate(certificate_id)
    if not cert:
        raise ResourceNotFoundError(f"Certificate '{certificate_id}' not found.")
    return cert


@router.get("/verify/{certificate_id}")
def verify_certificate_authenticity(certificate_id: str):
    """
    Independently verifies certificate against the circular EVM blockchain anchor (Stage 11).
    Recomputes hash, verifies commitment match, and validates ledger state.
    """
    is_valid, details = certificate_service.verify_certificate_independently(certificate_id)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=details
        )
    return details
