"""
backend/app/services/evidence_service.py — Cryptographic Evidence Pipeline Service.
Implements Section R2 and R4:
Evidence Files -> SHA-256 -> RFC 8785 Canonical Manifest -> Bundle SHA-256 -> keccak256 Commitment.
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from shared.domain.evidence_hasher import (
    canonicalize_json,
    hash_bytes_sha256,
    keccak256,
    compute_evidence_bundle_commitment,
)
from shared.schemas.evidence_bundle import (
    EvidenceFileRecord,
    AIInferenceObservation,
    MassBalanceVerificationResult,
    EvidenceBundle,
)
from shared.schemas.provenance import ProvenanceCategory
from backend.app.services.storage_service import storage_service
from backend.app.core.errors import EvidenceIntegrityError, ResourceNotFoundError


class EvidenceService:
    """Coordinates evidence hashing, canonical manifest compilation, and integrity checks."""

    def __init__(self):
        self._bundles: Dict[str, EvidenceBundle] = {}

    def compile_bundle(
        self,
        event_id: str,
        passport_id: str,
        evidence_file_ids: List[str],
        ai_observation: Optional[AIInferenceObservation],
        mass_balance_result: MassBalanceVerificationResult
    ) -> EvidenceBundle:
        """
        Compiles an EvidenceBundle, canonicalizes manifest per RFC 8785,
        and computes off-chain SHA-256 and on-chain keccak256 commitments.
        """
        file_records: List[EvidenceFileRecord] = []
        for fid in evidence_file_ids:
            rec = storage_service.get_record(fid)
            if not rec:
                raise ResourceNotFoundError(f"Evidence file record '{fid}' not found in storage index.")
            file_records.append(rec)

        ai_obs = ai_observation or AIInferenceObservation(
            model_provider="Deterministic Mock Fixture",
            model_version="fixture-v1",
            inference_timestamp=datetime.now(timezone.utc),
            detected_objects=["EV_Module_Cell"],
            estimated_materials={"Nickel": 165.6, "Cobalt": 55.8},
            confidence_scores={"overall": 0.95},
            anomaly_flags=[],
            provenance=ProvenanceCategory.AI_ESTIMATED
        )

        # Build raw manifest payload for canonicalization
        raw_manifest = {
            "bundle_schema_version": "1.0.0",
            "passport_id": passport_id,
            "event_id": event_id,
            "evidence_files": [f.model_dump(mode="json") for f in file_records],
            "ai_observation": ai_obs.model_dump(mode="json"),
            "mass_balance_result": mass_balance_result.model_dump(mode="json"),
        }

        sha256_digest, keccak_commitment = compute_evidence_bundle_commitment(raw_manifest)

        bundle = EvidenceBundle(
            bundle_id=f"EVB-{uuid.uuid4().hex[:12].upper()}",
            passport_id=passport_id,
            event_id=event_id,
            created_at=datetime.now(timezone.utc),
            evidence_files=file_records,
            ai_observation=ai_obs,
            mass_balance_result=mass_balance_result,
            canonical_manifest_sha256=sha256_digest,
            bundle_keccak256_commitment=keccak_commitment,
            blockchain_network="LOCAL TESTNET"
        )

        self._bundles[bundle.bundle_id] = bundle
        self._bundles[event_id] = bundle  # Index by event_id for fast lookup
        return bundle

    def get_bundle(self, bundle_or_event_id: str) -> Optional[EvidenceBundle]:
        return self._bundles.get(bundle_or_event_id)

    def verify_bundle_integrity(
        self,
        bundle: EvidenceBundle,
        expected_onchain_commitment: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Recomputes hash of evidence files and manifest from ground truth bytes.
        Flags tampering (Adversarial Case D).
        """
        # 1. Verify individual files against current storage
        for file_rec in bundle.evidence_files:
            current_bytes = storage_service.get_content(file_rec.file_id)
            if current_bytes is None:
                return False, f"Evidence file '{file_rec.file_id}' missing from physical storage."
            current_hash = hash_bytes_sha256(current_bytes)
            if current_hash != file_rec.sha256_hash:
                return False, (
                    f"EVIDENCE_INTEGRITY_FAILURE: Physical file '{file_rec.filename}' "
                    f"({file_rec.file_id}) content was mutated! "
                    f"Original SHA-256: {file_rec.sha256_hash}, Recomputed: {current_hash}."
                )

        # 2. Recompute manifest commitment
        raw_manifest = {
            "bundle_schema_version": "1.0.0",
            "passport_id": bundle.passport_id,
            "event_id": bundle.event_id,
            "evidence_files": [f.model_dump(mode="json") for f in bundle.evidence_files],
            "ai_observation": bundle.ai_observation.model_dump(mode="json") if bundle.ai_observation else None,
            "mass_balance_result": bundle.mass_balance_result.model_dump(mode="json"),
        }
        recomputed_sha256, recomputed_keccak = compute_evidence_bundle_commitment(raw_manifest)

        if recomputed_sha256 != bundle.canonical_manifest_sha256:
            return False, (
                f"EVIDENCE_INTEGRITY_FAILURE: Manifest hash mismatch. "
                f"Bundle: {bundle.canonical_manifest_sha256}, Recomputed: {recomputed_sha256}."
            )

        if recomputed_keccak != bundle.bundle_keccak256_commitment:
            return False, (
                f"EVIDENCE_INTEGRITY_FAILURE: keccak256 commitment mismatch. "
                f"Bundle: {bundle.bundle_keccak256_commitment}, Recomputed: {recomputed_keccak}."
            )

        # 3. Verify against on-chain anchor if provided
        if expected_onchain_commitment and recomputed_keccak.lower() != expected_onchain_commitment.lower():
            return False, (
                f"EVIDENCE_INTEGRITY_FAILURE: Recomputed commitment ({recomputed_keccak}) "
                f"does not match on-chain anchor ({expected_onchain_commitment})."
            )

        return True, "Evidence bundle integrity verified: all file digests and canonical commitments match."


evidence_service = EvidenceService()
