"""
backend/app/api/v1/passports.py — Digital Product Passport (DPP) API Endpoints.
Conforms strictly to shared.schemas.dpp.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from shared.schemas.dpp import DigitalProductPassport
from shared.domain.evidence_hasher import canonicalize_json, hash_bytes_sha256
from backend.app.services.blockchain_service import blockchain_service
from backend.app.core.errors import ReplayDetectedError, ResourceNotFoundError

router = APIRouter(prefix="/passports", tags=["Passports"])

# In-memory passport store
_PASSPORT_STORE: Dict[str, DigitalProductPassport] = {}


@router.post("", response_model=DigitalProductPassport, status_code=status.HTTP_201_CREATED)
def register_passport(passport: DigitalProductPassport):
    """
    Registers a new Digital Product Passport.
    Computes BoM hash and anchors initial record to the local EVM blockchain.
    """
    if passport.passport_id in _PASSPORT_STORE:
        raise ReplayDetectedError(f"Passport '{passport.passport_id}' already registered.")

    # Canonical BoM hash
    bom_data = [c.model_dump(mode="json") for c in passport.material_composition.components]
    bom_hash = "0x" + hash_bytes_sha256(canonicalize_json(bom_data))

    # Anchor on-chain
    tx_hash = blockchain_service.register_passport(
        passport_id=passport.passport_id,
        bom_hash=bom_hash,
        manufacturer=passport.manufacturer
    )

    _PASSPORT_STORE[passport.passport_id] = passport
    return passport


@router.get("/{passport_id}", response_model=DigitalProductPassport)
def get_passport(passport_id: str):
    """Retrieves a Digital Product Passport by identifier."""
    if passport_id not in _PASSPORT_STORE:
        raise ResourceNotFoundError(f"Passport '{passport_id}' not found.")
    passport = _PASSPORT_STORE[passport_id]
    # Sync current lifecycle state from blockchain service
    onchain_state = blockchain_service.get_lifecycle_state(passport_id)
    passport.current_lifecycle_state = onchain_state
    return passport


@router.get("", response_model=List[DigitalProductPassport])
def list_passports():
    """Lists all registered Digital Product Passports."""
    passports = []
    for pid, p in _PASSPORT_STORE.items():
        p.current_lifecycle_state = blockchain_service.get_lifecycle_state(pid)
        passports.append(p)
    return passports
