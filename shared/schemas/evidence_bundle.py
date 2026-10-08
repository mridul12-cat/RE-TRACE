"""
RE:TRACE Canonical Evidence Bundle Schema.

Enforces cryptographic evidence bundling per ORIGINAL_REQUEST.md:55-65:
Evidence Files -> SHA-256 Hashes -> Canonical Manifest (RFC 8785) -> Bundle SHA-256 / keccak256 commitment.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from shared.schemas.provenance import ProvenanceCategory


class EvidenceFileRecord(BaseModel):
    """
    Metadata and individual cryptographic hash for an uploaded physical evidence file.
    """
    file_id: str = Field(..., description="Unique file UUID")
    filename: str = Field(..., description="Original uploaded filename")
    mime_type: str = Field(..., description="Validated MIME type (e.g., 'image/jpeg', 'application/pdf')")
    file_size_bytes: int = Field(..., gt=0, description="Exact file size in bytes")
    sha256_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Hexadecimal SHA-256 digest of raw file contents",
    )
    provenance: ProvenanceCategory = Field(
        default=ProvenanceCategory.MEASURED,
        description="Provenance of the evidence capture",
    )


class AIInferenceObservation(BaseModel):
    """
    Structured computer vision telemetry from the AI observation layer.
    AI is strictly an observation/estimation layer, never an independent verifier.
    """
    model_provider: str = Field(..., description="AI service provider (e.g., 'Google Gemini', 'Deterministic Mock Fixture')")
    model_version: str = Field(..., description="Model version tag (e.g., 'gemini-2.5-flash', 'fixture-v1')")
    inference_timestamp: datetime = Field(..., description="UTC timestamp of inference execution")
    detected_objects: List[str] = Field(default_factory=list, description="Visual labels detected (e.g., ['EV_Module_Cell', 'Copper_Busbar'])")
    estimated_materials: Dict[str, float] = Field(default_factory=dict, description="Estimated material fractions or kg values")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="Confidence ratings in [0.0, 1.0]")
    anomaly_flags: List[str] = Field(default_factory=list, description="Visual anomalies detected (e.g., ['puncture', 'foreign_scrap'])")
    provenance: ProvenanceCategory = Field(
        default=ProvenanceCategory.AI_ESTIMATED,
        description="Always AI_ESTIMATED for model inference telemetry",
    )


class MassBalanceVerificationResult(BaseModel):
    """
    Detailed closed-form mathematical output of deterministic mass-balance evaluation.
    """
    intake_mass_kg: float = Field(..., ge=0.0, description="Gross intake mass used in evaluation")
    claimed_total_recovered_kg: float = Field(..., ge=0.0, description="Total sum of claimed recovered masses")
    expected_recoverable_kg: Dict[str, float] = Field(..., description="Nominal expected mass per material key")
    tolerance_bands_kg: Dict[str, Tuple[float, float]] = Field(..., description="Lower and upper tolerance boundaries (M_min, M_max)")
    discrepancies_kg: Dict[str, float] = Field(default_factory=dict, description="Deviation (claimed - expected) per material key")
    decision: str = Field(..., description="'VALID' (Verified), 'BORDERLINE' (Requires review), or 'IMPOSSIBLE' (Flagged)")
    mathematical_explanation: str = Field(..., description="Human-auditable physics-based explanation of the verdict")


class EvidenceBundle(BaseModel):
    """
    Canonical evidence bundle tying together physical files, AI observations,
    deterministic mass balance, RFC 8785 canonical manifest SHA-256, and on-chain commitment.
    """
    bundle_id: str = Field(..., description="Unique evidence bundle UUID")
    event_id: str = Field(..., description="Associated recycling event ID")
    passport_id: str = Field(..., description="Associated Digital Product Passport ID")
    evidence_files: List[EvidenceFileRecord] = Field(..., min_length=1, description="Uploaded evidence records with individual SHA-256 digests")
    ai_observation: AIInferenceObservation = Field(..., description="AI observation telemetry")
    mass_balance_result: MassBalanceVerificationResult = Field(..., description="Deterministic mass-balance evaluation record")
    canonical_manifest_sha256: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of the RFC 8785 canonical JSON manifest",
    )
    bundle_keccak256_commitment: str = Field(
        ...,
        min_length=64,
        max_length=66,
        description="EVM keccak256 commitment for on-chain anchoring (hex string, optionally 0x-prefixed)",
    )
    blockchain_tx_hash: Optional[str] = Field(default=None, description="Transaction hash on EVM ledger if anchored")
    blockchain_network: str = Field(default="LOCAL TESTNET", description="Explicit network label per R5 truthfulness")
    created_at: datetime = Field(..., description="UTC creation timestamp")
