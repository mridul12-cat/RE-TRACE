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
    if not _PASSPORT_STORE:
        seed_default_passports()
    if passport_id not in _PASSPORT_STORE:
        raise ResourceNotFoundError(f"Passport '{passport_id}' not found.")
    passport = _PASSPORT_STORE[passport_id]
    # Sync current lifecycle state from blockchain service
    onchain_state = blockchain_service.get_lifecycle_state(passport_id)
    passport.current_lifecycle_state = onchain_state
    return passport


def seed_default_passports(force_reset: bool = False) -> List[DigitalProductPassport]:
    """
    Seeds standard baseline Digital Product Passports grounded in EU Battery Regulation
    reference fixtures so that Custom Verification has legitimate candidate passports.
    Includes:
    1. DPP-EV-NMC622-2026-M04 in RECYCLING_PENDING (eligible for recycling verification)
    2. DPP-CONSUMER-LCO-2026-B10 in MANUFACTURED (demonstrates non-eligible status check)
    """
    from datetime import datetime, timezone
    from shared.fixtures.reference_materials import (
        EV_BATTERY_NMC_622_COMPOSITION,
        SMARTPHONE_LCO_COMPOSITION,
    )
    from shared.domain.lifecycle import LifecycleState, AuthorizedRole

    # 1. EV Traction Battery in RECYCLING_PENDING
    pid_ev = "DPP-EV-NMC622-2026-M04"
    if force_reset or pid_ev not in _PASSPORT_STORE or pid_ev not in blockchain_service._passports:
        now = datetime.now(timezone.utc)
        dpp_ev = DigitalProductPassport(
            passport_id=pid_ev,
            product_id="SKU-EV-NMC622-48V",
            product_name="VoltMax EV Traction Battery Module NMC 622 (24V 6S2P)",
            product_category="EV_BATTERY",
            manufacturer="NorthVolt Energy Systems AB",
            manufacturing_date=datetime(2026, 3, 15, 8, 30, tzinfo=timezone.utc),
            initial_total_mass_kg=25.0,
            material_composition=EV_BATTERY_NMC_622_COMPOSITION,
            current_lifecycle_state=LifecycleState.MANUFACTURED,
            created_at=now,
            updated_at=now,
        )
        bom_data = [c.model_dump(mode="json") for c in dpp_ev.material_composition.components]
        bom_hash = "0x" + hash_bytes_sha256(canonicalize_json(bom_data))

        # Clear existing on-chain lifecycle state if force_reset
        if force_reset:
            blockchain_service._passports.pop(pid_ev, None)
            blockchain_service._lifecycle_states.pop(pid_ev, None)

        if pid_ev not in blockchain_service._passports:
            blockchain_service.register_passport(
                passport_id=pid_ev,
                bom_hash=bom_hash,
                manufacturer="0x1111111111111111111111111111111111111111"
            )
            blockchain_service.transition_state(pid_ev, LifecycleState.IN_USE, AuthorizedRole.MANUFACTURER)
            blockchain_service.transition_state(pid_ev, LifecycleState.RETURNED, AuthorizedRole.COLLECTION_AGENT)
            blockchain_service.transition_state(pid_ev, LifecycleState.RECYCLING_PENDING, AuthorizedRole.RECYCLER)
        dpp_ev.current_lifecycle_state = blockchain_service.get_lifecycle_state(pid_ev)
        _PASSPORT_STORE[pid_ev] = dpp_ev

    # 2. Consumer Smartphone Battery in MANUFACTURED (demonstrating eligibility gating)
    pid_phone = "DPP-CONSUMER-LCO-2026-B10"
    if force_reset or pid_phone not in _PASSPORT_STORE or pid_phone not in blockchain_service._passports:
        now = datetime.now(timezone.utc)
        dpp_phone = DigitalProductPassport(
            passport_id=pid_phone,
            product_id="SKU-PHONE-BATT-4500",
            product_name="UltraPower 4500mAh Smartphone Li-ion Pouch Cell",
            product_category="CONSUMER_BATTERY",
            manufacturer="Apex Energy Technologies Inc.",
            manufacturing_date=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
            initial_total_mass_kg=0.045,
            material_composition=SMARTPHONE_LCO_COMPOSITION,
            current_lifecycle_state=LifecycleState.MANUFACTURED,
            created_at=now,
            updated_at=now,
        )
        bom_data_phone = [c.model_dump(mode="json") for c in dpp_phone.material_composition.components]
        bom_hash_phone = "0x" + hash_bytes_sha256(canonicalize_json(bom_data_phone))

        if force_reset:
            blockchain_service._passports.pop(pid_phone, None)
            blockchain_service._lifecycle_states.pop(pid_phone, None)

        if pid_phone not in blockchain_service._passports:
            blockchain_service.register_passport(
                passport_id=pid_phone,
                bom_hash=bom_hash_phone,
                manufacturer="0x2222222222222222222222222222222222222222"
            )
        dpp_phone.current_lifecycle_state = blockchain_service.get_lifecycle_state(pid_phone)
        _PASSPORT_STORE[pid_phone] = dpp_phone

    return list(_PASSPORT_STORE.values())


@router.get("", response_model=List[DigitalProductPassport])
def list_passports():
    """Lists all registered Digital Product Passports."""
    if not _PASSPORT_STORE:
        seed_default_passports()
    passports = []
    for pid, p in _PASSPORT_STORE.items():
        p.current_lifecycle_state = blockchain_service.get_lifecycle_state(pid)
        passports.append(p)
    return passports


@router.post("/seed", response_model=List[DigitalProductPassport])
def seed_passports_endpoint(force: bool = False):
    """Seeds baseline reference DPPs (e.g. for testing and demonstrations)."""
    return seed_default_passports(force_reset=force)
