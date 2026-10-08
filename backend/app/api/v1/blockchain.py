"""
backend/app/api/v1/blockchain.py — Local EVM Ledger Status & Inspection API.
Enforces Section R5: Truthfulness and offline failure handling (Adversarial Case J).
"""

from fastapi import APIRouter
from backend.app.services.blockchain_service import blockchain_service

router = APIRouter(prefix="/blockchain", tags=["Blockchain"])


@router.get("/status")
def get_blockchain_status():
    """
    Returns current blockchain connection state.
    Strictly labelled 'LOCAL TESTNET' per Section R5 Truthfulness.
    """
    return blockchain_service.get_status()


@router.post("/simulate-disconnect")
def simulate_disconnect():
    """Simulates RPC node outage for offline behavior testing (Adversarial Case J)."""
    blockchain_service.simulate_rpc_disconnect()
    return {"status": "DISCONNECTED", "is_connected": False}


@router.post("/simulate-reconnect")
def simulate_reconnect():
    """Re-establishes simulated RPC connection."""
    blockchain_service.simulate_rpc_reconnect()
    return {"status": "CONNECTED", "is_connected": True}


@router.get("/events")
def list_anchored_events():
    """Lists all anchored recycling events on the circular ledger."""
    return [
        {
            "event_id": e.event_id,
            "passport_id": e.passport_id,
            "evidence_commitment": e.evidence_commitment,
            "recycler_address": e.recycler_address,
            "tx_hash": e.tx_hash,
            "block_number": e.block_number,
            "timestamp": e.timestamp,
        }
        for e in blockchain_service.list_events()
    ]


@router.get("/passports")
def list_onchain_passports():
    """Lists all passports registered on the blockchain."""
    return blockchain_service.list_passports()


@router.get("/certificates")
def list_onchain_certificates():
    """Lists all certificates anchored on the blockchain."""
    return [
        {
            "certificate_id": c.certificate_id,
            "event_id": c.event_id,
            "passport_id": c.passport_id,
            "certificate_hash": c.certificate_hash,
            "evidence_commitment": c.evidence_commitment,
            "tx_hash": c.tx_hash,
            "block_number": c.block_number,
            "timestamp": c.timestamp,
        }
        for c in blockchain_service.list_certificates()
    ]
