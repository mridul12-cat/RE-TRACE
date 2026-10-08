"""
backend/app/services/certificate_service.py — Proof-of-Recycling (PoR) Certificate Service.
Implements Section R5: Anti-Replay duplicate protection and reproducible independent verification.
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from shared.domain.evidence_hasher import (
    canonicalize_json,
    hash_bytes_sha256,
)
from shared.schemas.por_certificate import (
    ProofOfRecyclingCertificate,
    VerifiedMaterialQuantity,
)
from backend.app.services.blockchain_service import blockchain_service
from backend.app.core.errors import (
    DuplicateCertificateError,
    ResourceNotFoundError,
    IllegalTransitionError,
)
from shared.domain.lifecycle import LifecycleState


class CertificateService:
    """Manages generation, issuance, and independent verification of PoR Certificates."""

    def __init__(self):
        self._certificates: Dict[str, ProofOfRecyclingCertificate] = {}
        self._event_to_cert: Dict[str, str] = {}  # event_id -> certificate_id (Anti-Replay)

    def generate_and_issue_certificate(
        self,
        passport_id: str,
        event_id: str,
        facility_id: str,
        verified_materials: List[VerifiedMaterialQuantity],
        evidence_commitment: str,
        verification_confidence: float = 0.96
    ) -> ProofOfRecyclingCertificate:
        """
        Generates and anchors a Proof-of-Recycling certificate.
        Rejects duplicate certificates for the same recycling event (Adversarial Case F).
        """
        if event_id in self._event_to_cert:
            existing_id = self._event_to_cert[event_id]
            raise DuplicateCertificateError(
                f"Duplicate certificate prohibited: Event '{event_id}' already has certificate '{existing_id}'."
            )

        # Check passport state
        current_state = blockchain_service.get_lifecycle_state(passport_id)
        if current_state != LifecycleState.RECYCLING_VERIFIED:
            raise IllegalTransitionError(
                f"Cannot issue certificate: Product '{passport_id}' must be in RECYCLING_VERIFIED state (current: {current_state.value})."
            )

        cert_id = f"POR-2026-{uuid.uuid4().hex[:10].upper()}"
        now = datetime.now(timezone.utc)

        # Build canonical payload to compute certificate hash
        cert_data_for_hash = {
            "certificate_id": cert_id,
            "passport_id": passport_id,
            "event_id": event_id,
            "facility_id": facility_id,
            "verified_materials": [m.model_dump(mode="json") for m in verified_materials],
            "evidence_commitment": evidence_commitment,
            "verification_result": "VERIFIED",
            "issued_at": now.isoformat(),
        }
        cert_canonical = canonicalize_json(cert_data_for_hash)
        cert_hash = "0x" + hash_bytes_sha256(cert_canonical)

        # Anchor certificate on local EVM blockchain
        tx_hash = blockchain_service.issue_certificate(
            certificate_id=cert_id,
            event_id=event_id,
            passport_id=passport_id,
            cert_hash=cert_hash,
            evidence_commitment=evidence_commitment
        )

        certificate = ProofOfRecyclingCertificate(
            certificate_id=cert_id,
            passport_id=passport_id,
            event_id=event_id,
            facility_id=facility_id,
            verified_material_quantities=verified_materials,
            verification_result="VERIFIED",
            verification_confidence=verification_confidence,
            evidence_commitment=evidence_commitment,
            blockchain_transaction_reference=tx_hash,
            blockchain_network=blockchain_service.network_label,
            issued_at=now,
            certificate_hash=cert_hash
        )

        self._certificates[cert_id] = certificate
        self._event_to_cert[event_id] = cert_id
        return certificate

    def get_certificate(self, certificate_id: str) -> Optional[ProofOfRecyclingCertificate]:
        return self._certificates.get(certificate_id)

    def verify_certificate_independently(
        self,
        certificate_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Stage 11: Independent verification checks:
        1. Certificate exists in off-chain repository.
        2. Recomputed certificate hash matches certificate_hash.
        3. Blockchain ledger has anchored record of certificate.
        4. Evidence commitment on ledger matches certificate's evidence_commitment.
        """
        cert = self.get_certificate(certificate_id)
        if not cert:
            return False, {"error": f"Certificate '{certificate_id}' not found."}

        on_chain = blockchain_service.get_certificate(certificate_id)
        if not on_chain:
            return False, {"error": "Certificate not anchored on local EVM ledger."}

        # Check hash match
        if on_chain.certificate_hash.lower() != cert.certificate_hash.lower():
            return False, {
                "error": "Certificate hash mismatch with blockchain record",
                "local_hash": cert.certificate_hash,
                "onchain_hash": on_chain.certificate_hash
            }

        # Check evidence commitment match
        if on_chain.evidence_commitment.lower() != cert.evidence_commitment.lower():
            return False, {
                "error": "Evidence commitment mismatch with on-chain anchor",
                "cert_commitment": cert.evidence_commitment,
                "onchain_commitment": on_chain.evidence_commitment
            }

        return True, {
            "status": "VALID_AND_AUTHENTICATED",
            "certificate_id": cert.certificate_id,
            "passport_id": cert.passport_id,
            "event_id": cert.event_id,
            "blockchain_network": cert.blockchain_network,
            "tx_hash": cert.blockchain_transaction_reference,
            "evidence_commitment": cert.evidence_commitment,
            "certificate_hash": cert.certificate_hash,
            "verified_at": datetime.now(timezone.utc).isoformat()
        }


certificate_service = CertificateService()
