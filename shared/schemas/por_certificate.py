"""
RE:TRACE Canonical Proof-of-Recycling (PoR) Certificate Schema.

Represents an immutable, cryptographically verifiable certificate issued upon successful
deterministic mass-balance verification and blockchain commitment anchoring.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class VerifiedMaterialQuantity(BaseModel):
    """
    Certified recovered secondary material quantity verified by the system.
    """
    material_name: str = Field(..., description="Certified material name (e.g., 'Cobalt', 'Nickel')")
    recovered_mass_kg: float = Field(..., gt=0.0, description="Verified mass recovered in kg")
    purity_pct: float = Field(default=95.0, ge=0.0, le=100.0, description="Assayed purity percentage")
    recovery_yield_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Effective process recovery yield percentage achieved",
    )


class ProofOfRecyclingCertificate(BaseModel):
    """
    Canonical Proof-of-Recycling Certificate tied to product passport and recycling event.
    """
    certificate_id: str = Field(..., description="Unique certificate UUID")
    passport_id: str = Field(..., description="Associated Digital Product Passport identifier")
    event_id: str = Field(..., description="Associated unique recycling event identifier")
    facility_id: str = Field(..., description="Certified recycling facility license identifier")
    verified_material_quantities: List[VerifiedMaterialQuantity] = Field(
        ...,
        min_length=1,
        description="Quantities of verified recovered secondary materials",
    )
    verification_result: str = Field(
        default="VERIFIED",
        description="Canonical outcome (strictly 'VERIFIED' for issued certificates)",
    )
    verification_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Aggregate confidence score across physical measurements and observations",
    )
    evidence_commitment: str = Field(
        ...,
        description="Cryptographic commitment (keccak256 / SHA-256) anchored to the blockchain",
    )
    blockchain_transaction_reference: str = Field(
        ...,
        description="Transaction hash or receipt reference on the circular ledger",
    )
    blockchain_network: str = Field(
        default="LOCAL TESTNET",
        description="Explicit blockchain network identifier (e.g., 'LOCAL TESTNET', 'LOCAL DEVELOPMENT BLOCKCHAIN')",
    )
    issued_at: datetime = Field(..., description="UTC certificate issuance timestamp")
    certificate_hash: str = Field(
        ...,
        min_length=64,
        max_length=66,
        description="Cryptographic SHA-256 or keccak256 digest over the canonical certificate fields",
    )
