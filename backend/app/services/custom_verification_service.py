"""
backend/app/services/custom_verification_service.py — Custom Verification Orchestration Service.

Orchestrates the existing verification pipeline for user-submitted recycling events:
1. Digital Product Passport lookup and lifecycle eligibility check (RECYCLING_PENDING).
2. Input validation (positive mass, claimed materials, purity, evidence files).
3. Optional dual-mode AI visual observation (observation only; never verification decision).
4. Deterministic mass-balance evaluation (closed-form physics & BoM priors).
5. Canonical evidence bundle compilation and cryptographic commitment (RFC 8785).
6. Evidence integrity verification (SHA-256 and keccak256 matching).
7. Blockchain state transition & anchoring on LOCAL TESTNET (Chain ID: 31337).
8. Proof-of-Recycling (PoR) certificate issuance when legitimately verified.
"""

import math
import uuid
import re
import threading
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from shared.schemas.provenance import ProvenanceCategory
from shared.schemas.recycling_event import RecyclingEvent, ClaimedMaterial
from shared.schemas.evidence_bundle import (
    EvidenceBundle,
    AIInferenceObservation,
    MassBalanceVerificationResult,
)
from shared.schemas.por_certificate import (
    VerifiedMaterialQuantity,
    ProofOfRecyclingCertificate,
)
from shared.domain.lifecycle import LifecycleState, AuthorizedRole
from ml.models.vision_schemas import AIObservationResult

from backend.app.core.errors import (
    ResourceNotFoundError,
    ReplayDetectedError,
    IllegalTransitionError,
    RETraceBaseError,
)
from backend.app.services.storage_service import storage_service
from backend.app.services.mass_balance_service import mass_balance_service
from backend.app.services.evidence_service import evidence_service
from backend.app.services.blockchain_service import blockchain_service
from backend.app.services.certificate_service import certificate_service
from backend.app.api.v1.ai import ai_service
from backend.app.api.v1.passports import _PASSPORT_STORE, seed_default_passports
from backend.app.api.v1.recycling import get_event_by_id, submit_recycling_event

logger = logging.getLogger("retrace.custom_verification")


def _is_safe_id(val: str, max_len: int = 128) -> bool:
    """Validates that an identifier contains no path traversal, control characters, or invalid symbols."""
    if not val or not isinstance(val, str):
        return False
    clean = val.strip()
    if not clean or len(clean) > max_len:
        return False
    if any(c in clean for c in ("\0", "\n", "\r", "\t", "/", "\\")):
        return False
    if ".." in clean:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_.:-]+$", clean))


class CustomVerificationService:
    """
    Orchestration service composing existing core services for custom recycling verifications.
    Does not duplicate domain algorithms or create alternative ledger/hashing paths.
    """

    def __init__(self):
        self._lock = threading.Lock()

    def process_custom_verification(
        self,
        passport_id: str,
        facility_id: str,
        operator_id: str,
        intake_gross_mass_kg: float,
        claimed_materials_data: List[Dict[str, Any]],
        evidence_file_ids: List[str],
        intake_mass_provenance: ProvenanceCategory = ProvenanceCategory.OBSERVED,
        processing_method: str = "HYDROMETALLURGICAL",
        event_id: Optional[str] = None,
        run_ai_observation: bool = False,
        ai_file_id: Optional[str] = None,
        ai_force_mode: Optional[str] = None,
        ai_fixture_override: Optional[str] = None,
        scale_uncertainty_pct: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end custom recycling verification workflow.
        Returns unified audit result dictionary.
        """
        # ---------------------------------------------------------------------
        # 1. Event Identifier Anti-Replay Guard (Evaluated First for Case E)
        # ---------------------------------------------------------------------
        if event_id:
            clean_event_id = str(event_id).strip()
            if not clean_event_id:
                raise RETraceBaseError(
                    "Event ID cannot be whitespace only.",
                    status_code=400,
                    error_code="MALFORMED_EVENT_ID",
                )
            if not _is_safe_id(clean_event_id):
                raise RETraceBaseError(
                    f"Malformed event ID '{clean_event_id}': illegal characters or path traversal detected.",
                    status_code=400,
                    error_code="MALFORMED_EVENT_ID",
                )
            if get_event_by_id(clean_event_id) or blockchain_service.get_event(clean_event_id):
                raise ReplayDetectedError(
                    f"Replay detected: Recycling event '{clean_event_id}' has already been ingested."
                )
            assigned_event_id = clean_event_id
        else:
            assigned_event_id = f"REV-2026-CUSTOM-{uuid.uuid4().hex[:8].upper()}"

        # ---------------------------------------------------------------------
        # 2. Passport Lookup & Lifecycle State Eligibility Validation
        # ---------------------------------------------------------------------
        pid = (passport_id or "").strip()
        if not pid:
            raise RETraceBaseError("Missing passport identifier.", status_code=400, error_code="MISSING_PASSPORT")
        if not _is_safe_id(pid):
            raise RETraceBaseError(
                f"Malformed passport ID '{pid}': illegal characters or path traversal detected.",
                status_code=400,
                error_code="MALFORMED_PASSPORT_ID",
            )

        if not _PASSPORT_STORE:
            seed_default_passports()

        passport = _PASSPORT_STORE.get(pid)
        if not passport:
            raise ResourceNotFoundError(f"Passport '{pid}' not found.")

        current_lifecycle = blockchain_service.get_lifecycle_state(pid)
        if current_lifecycle != LifecycleState.RECYCLING_PENDING:
            raise IllegalTransitionError(
                f"Passport '{pid}' is in lifecycle state '{current_lifecycle.value}'. "
                f"Only passports in 'RECYCLING_PENDING' are eligible for recycling verification."
            )

        # ---------------------------------------------------------------------
        # 3. Intake Mass Validation
        # ---------------------------------------------------------------------
        if not math.isfinite(intake_gross_mass_kg) or intake_gross_mass_kg <= 0.0:
            raise RETraceBaseError(
                f"Gross intake mass must be strictly positive and finite (> 0); received {intake_gross_mass_kg} kg.",
                status_code=400,
                error_code="INVALID_INTAKE_MASS",
            )

        # ---------------------------------------------------------------------
        # 4. Claimed Materials Validation & Provenance Preservation
        # ---------------------------------------------------------------------
        if not claimed_materials_data or len(claimed_materials_data) == 0:
            raise RETraceBaseError(
                "Claimed materials list cannot be empty.",
                status_code=400,
                error_code="EMPTY_CLAIMED_MATERIALS",
            )

        claimed_materials: List[ClaimedMaterial] = []
        for idx, item in enumerate(claimed_materials_data):
            mat_name = str(item.get("material_name", "")).strip()
            if not mat_name:
                raise RETraceBaseError(
                    f"Material name in claim #{idx + 1} cannot be empty.",
                    status_code=400,
                    error_code="INVALID_MATERIAL_NAME",
                )

            m_val = float(item.get("claimed_mass_kg", 0.0))
            if not math.isfinite(m_val) or m_val < 0.0:
                raise RETraceBaseError(
                    f"Claimed mass for '{mat_name}' cannot be negative or non-finite ({m_val} kg).",
                    status_code=400,
                    error_code="NEGATIVE_MATERIAL_MASS",
                )

            purity = float(item.get("purity_pct", 95.0))
            if not math.isfinite(purity) or purity < 0.0 or purity > 100.0:
                raise RETraceBaseError(
                    f"Purity % for '{mat_name}' must be between 0.0 and 100.0; received {purity}%.",
                    status_code=400,
                    error_code="INVALID_PURITY",
                )

            prov_raw = item.get("provenance", ProvenanceCategory.OBSERVED)
            if isinstance(prov_raw, ProvenanceCategory):
                prov = prov_raw
            else:
                try:
                    prov = ProvenanceCategory(str(prov_raw).upper())
                except ValueError:
                    prov = ProvenanceCategory.OBSERVED

            claimed_materials.append(
                ClaimedMaterial(
                    material_name=mat_name,
                    claimed_mass_kg=m_val,
                    purity_pct=purity,
                    provenance=prov,
                )
            )

        # ---------------------------------------------------------------------
        # 5. Evidence References Validation
        # ---------------------------------------------------------------------
        if not evidence_file_ids or len(evidence_file_ids) == 0:
            raise RETraceBaseError(
                "At least one physical evidence file is required for verification.",
                status_code=400,
                error_code="MISSING_EVIDENCE",
            )

        clean_evidence_ids: List[str] = []
        for fid in evidence_file_ids:
            clean_fid = str(fid).strip()
            if not clean_fid or not _is_safe_id(clean_fid):
                raise RETraceBaseError(
                    f"Malformed evidence file ID '{clean_fid}': illegal characters or path traversal detected.",
                    status_code=400,
                    error_code="MALFORMED_EVIDENCE_ID",
                )
            rec = storage_service.get_record(clean_fid)
            if not rec or storage_service.get_content(clean_fid) is None:
                raise ResourceNotFoundError(f"Evidence file '{clean_fid}' not found in storage index.")
            clean_evidence_ids.append(clean_fid)

        # ---------------------------------------------------------------------
        # 6. Optional AI Visual Observation (Trust Segregation per ADR-001)
        # ---------------------------------------------------------------------
        ai_result: Optional[AIObservationResult] = None
        ai_inference_obs: Optional[AIInferenceObservation] = None
        ai_notice: Optional[str] = None

        if run_ai_observation:
            target_ai_fid = ai_file_id if (ai_file_id and ai_file_id in clean_evidence_ids) else clean_evidence_ids[0]
            try:
                content = storage_service.get_content(target_ai_fid)
                record = storage_service.get_record(target_ai_fid)
                if content and record:
                    ai_result = ai_service.observe(
                        file_bytes=content,
                        filename=record.filename,
                        mime_type=record.mime_type,
                        product_id=pid,
                        force_mode=ai_force_mode,
                        fixture_override=ai_fixture_override,
                    )
                    ai_inference_obs = AIInferenceObservation(
                        model_provider=ai_result.provider,
                        model_version=ai_result.model,
                        inference_timestamp=ai_result.inference_timestamp,
                        detected_objects=[item.label for item in ai_result.detected_items],
                        estimated_materials=ai_result.material_estimates,
                        confidence_scores={"overall": ai_result.confidence},
                        anomaly_flags=ai_result.anomaly_flags,
                        provenance=ai_result.provenance_category,
                    )
                    ai_notice = (
                        "AI observes evidence; deterministic verification makes the decision. "
                        "Material estimation used as contextual prior only."
                    )
            except Exception as e:
                logger.warning(f"AI observation failed/unavailable: {e}. Gracefully continuing deterministic verification.")
                ai_notice = f"AI observation unavailable ({str(e)}). Deterministic verification proceeded without AI observation."
        else:
            ai_notice = "AI observation skipped by user. Deterministic verification executed directly."

        # ---------------------------------------------------------------------
        # 7. Ingest Canonical Recycling Event via Existing API Handler (Thread-Safe)
        # ---------------------------------------------------------------------
        recycling_event = RecyclingEvent(
            event_id=assigned_event_id,
            passport_id=passport.passport_id,
            facility_id=str(facility_id).strip() or "FAC-CUSTOM-01",
            operator_id=str(operator_id).strip() or "OP-CUSTOM-01",
            intake_gross_mass_kg=intake_gross_mass_kg,
            intake_mass_provenance=intake_mass_provenance,
            claimed_materials=claimed_materials,
            evidence_file_ids=clean_evidence_ids,
            processing_method=processing_method or "HYDROMETALLURGICAL",
            timestamp=datetime.now(timezone.utc),
            status="SUBMITTED",
        )
        with self._lock:
            if get_event_by_id(assigned_event_id) or blockchain_service.get_event(assigned_event_id):
                raise ReplayDetectedError(
                    f"Replay detected: Recycling event '{assigned_event_id}' has already been ingested."
                )
            submit_recycling_event(recycling_event)

        # ---------------------------------------------------------------------
        # 8. Deterministic Mass-Balance Evaluation (Closed-Form Physics)
        # ---------------------------------------------------------------------
        mb_result: MassBalanceVerificationResult = mass_balance_service.evaluate(
            intake_mass_kg=intake_gross_mass_kg,
            composition=passport.material_composition,
            claimed_materials=claimed_materials,
            scale_uncertainty_pct=scale_uncertainty_pct,
        )
        mb_dec_str = mb_result.decision.value if hasattr(mb_result.decision, "value") else str(mb_result.decision)

        # ---------------------------------------------------------------------
        # 9. Compile Evidence Bundle & Cryptographic Commitment (RFC 8785)
        # ---------------------------------------------------------------------
        bundle: EvidenceBundle = evidence_service.compile_bundle(
            event_id=assigned_event_id,
            passport_id=passport.passport_id,
            evidence_file_ids=clean_evidence_ids,
            ai_observation=ai_inference_obs,
            mass_balance_result=mb_result,
        )

        # ---------------------------------------------------------------------
        # 10. Verify Evidence Integrity Against Current Disk State
        # ---------------------------------------------------------------------
        is_integrity_valid, integrity_msg = evidence_service.verify_bundle_integrity(bundle=bundle)
        integrity_status = "VERIFIED" if is_integrity_valid else "BREACHED"

        # ---------------------------------------------------------------------
        # 11. State Machine Progression, Ledger Anchoring & Certificate Issuance
        # ---------------------------------------------------------------------
        tx_hash: Optional[str] = None
        block_number: Optional[int] = None
        is_anchored = False
        certificate: Optional[ProofOfRecyclingCertificate] = None
        certificate_block_reason: Optional[str] = None
        overall_decision: str

        if not is_integrity_valid:
            overall_decision = "EVIDENCE_INTEGRITY_FAILURE"
            blockchain_service.flag_product(
                passport_id=passport.passport_id,
                reason=f"EVIDENCE_INTEGRITY_FAILURE: {integrity_msg[:180]}",
                event_id=assigned_event_id,
            )
            current_state = LifecycleState.FLAGGED.value
            certificate_block_reason = f"Evidence integrity breach detected: {integrity_msg}"

        elif mb_dec_str == "VALID":
            overall_decision = "VERIFIED"
            # Anchor evidence commitment on local EVM ledger
            tx_hash = blockchain_service.anchor_evidence(
                event_id=assigned_event_id,
                passport_id=passport.passport_id,
                evidence_commitment=bundle.bundle_keccak256_commitment,
            )
            is_anchored = True
            anchored_rec = blockchain_service.get_event(assigned_event_id)
            block_number = anchored_rec.block_number if anchored_rec else blockchain_service.current_block

            # Transition lifecycle state to RECYCLING_VERIFIED
            blockchain_service.transition_state(
                passport_id=passport.passport_id,
                target_state=LifecycleState.RECYCLING_VERIFIED,
                actor_role=AuthorizedRole.VERIFIER_SERVICE,
            )
            current_state = LifecycleState.RECYCLING_VERIFIED.value

            # Calculate verified material quantities for certificate issuance
            verified_materials: List[VerifiedMaterialQuantity] = []
            for claim in claimed_materials:
                if claim.claimed_mass_kg <= 0.0:
                    continue
                try:
                    comp = passport.material_composition.get_component(claim.material_name)
                    w_ref = comp.percentage / 100.0
                    loss_pct = comp.expected_yield_loss_pct / 100.0
                    expected_yield = 100.0 * (1.0 - loss_pct)
                    ref_mass = intake_gross_mass_kg * w_ref
                    raw_yield = (claim.claimed_mass_kg / ref_mass * 100.0) if ref_mass > 0 else expected_yield
                except KeyError:
                    raw_yield = 100.0

                eff_yield = min(100.0, max(0.0, raw_yield))

                verified_materials.append(
                    VerifiedMaterialQuantity(
                        material_name=claim.material_name,
                        recovered_mass_kg=claim.claimed_mass_kg,
                        purity_pct=claim.purity_pct,
                        recovery_yield_pct=round(eff_yield, 2),
                    )
                )

            if verified_materials:
                certificate = certificate_service.generate_and_issue_certificate(
                    passport_id=passport.passport_id,
                    event_id=assigned_event_id,
                    facility_id=recycling_event.facility_id,
                    verified_materials=verified_materials,
                    evidence_commitment=bundle.bundle_keccak256_commitment,
                    verification_confidence=0.965,
                )
            else:
                certificate = None
                certificate_block_reason = "No positive recovered material quantities claimed for certificate issuance."

        elif mb_dec_str == "BORDERLINE":
            overall_decision = "REVIEW"
            current_state = blockchain_service.get_lifecycle_state(passport.passport_id).value
            certificate_block_reason = (
                "Mass balance evaluation result is BORDERLINE. Certificate issuance is held "
                "pending authorized supervisor/auditor assay titration review."
            )

        else:  # IMPOSSIBLE
            overall_decision = "FLAGGED"
            blockchain_service.flag_product(
                passport_id=passport.passport_id,
                reason=f"Mass balance violation: {mb_result.mathematical_explanation[:200]}",
                event_id=assigned_event_id,
            )
            current_state = LifecycleState.FLAGGED.value
            certificate_block_reason = (
                f"Stoichiometric / conservation-of-mass violation (IMPOSSIBLE): "
                f"{mb_result.mathematical_explanation[:250]}"
            )

        # ---------------------------------------------------------------------
        # 12. Claim-by-Claim Breakdown & Concise Explanation (v1.1.1 UX Hardening)
        # ---------------------------------------------------------------------
        claims_breakdown: List[Dict[str, Any]] = []
        explanation_parts = [p.strip() for p in mb_result.mathematical_explanation.split(" | ")]
        gross_violation = any("Gross conservation of mass violated" in p for p in explanation_parts)

        for claim in claimed_materials:
            c_name = claim.material_name.strip()
            c_mass = claim.claimed_mass_kg

            # Look up matching component in BoM (case-insensitive)
            matched_comp = None
            canonical_name = c_name
            for bom_comp in passport.material_composition.components:
                if bom_comp.material_name.strip().lower() == c_name.lower():
                    matched_comp = bom_comp
                    canonical_name = bom_comp.material_name.strip()
                    break

            c_status = "VALID"
            c_reason = ""

            if gross_violation:
                c_status = "IMPOSSIBLE"
                c_reason = "Gross intake conservation violated."
            elif matched_comp is None:
                c_status = "IMPOSSIBLE"
                c_reason = f'Material "{c_name}" is not present in the product Bill of Materials.'
            else:
                for part in explanation_parts:
                    if canonical_name.lower() in part.lower():
                        if part.startswith("IMPOSSIBLE:"):
                            c_status = "IMPOSSIBLE"
                            c_reason = part[len("IMPOSSIBLE:"):].strip()
                            break
                        elif part.startswith("BORDERLINE:"):
                            c_status = "BORDERLINE"
                            c_reason = part[len("BORDERLINE:"):].strip()
                            break
                        elif part.startswith("VALID:"):
                            c_status = "VALID"
                            c_reason = part[len("VALID:"):].strip()
                            break

            claims_breakdown.append({
                "material_name": c_name,
                "claimed_mass_kg": round(c_mass, 4),
                "status": c_status,
                "reason": c_reason,
                "expected_kg": mb_result.expected_recoverable_kg.get(canonical_name),
                "tolerance_band": mb_result.tolerance_bands_kg.get(canonical_name),
                "discrepancy_kg": mb_result.discrepancies_kg.get(canonical_name),
            })

        if mb_dec_str == "IMPOSSIBLE":
            failing_claims = [c for c in claims_breakdown if c["status"] == "IMPOSSIBLE"]
            if failing_claims:
                count_str = f"{len(failing_claims)} claim{'s' if len(failing_claims) > 1 else ''} failed deterministic verification."
                reasons_str = "\n".join(f"- {c['reason']}" for c in failing_claims if c['reason'])
                concise_explanation = f"{count_str}\n{reasons_str}".strip()
            else:
                concise_explanation = mb_result.mathematical_explanation
        elif mb_dec_str == "BORDERLINE":
            borderline_claims = [c for c in claims_breakdown if c["status"] == "BORDERLINE"]
            if borderline_claims:
                count_str = f"{len(borderline_claims)} claim{'s' if len(borderline_claims) > 1 else ''} deviated from nominal tolerance envelope."
                reasons_str = "\n".join(f"- {c['reason']}" for c in borderline_claims if c['reason'])
                concise_explanation = f"{count_str}\n{reasons_str}\nRequires supervisor audit of assay titration logs.".strip()
            else:
                concise_explanation = mb_result.mathematical_explanation
        else:
            concise_explanation = "All declared recovery claims satisfy stoichiometric conservation and BAT yield envelopes."

        return {
            "event_id": assigned_event_id,
            "passport_id": passport.passport_id,
            "overall_decision": overall_decision,
            "mass_balance_decision": mb_dec_str,
            "evidence_integrity_status": integrity_status,
            "evidence_integrity_message": integrity_msg,
            "lifecycle_state": current_state,
            "mathematical_explanation": mb_result.mathematical_explanation,
            "concise_explanation": concise_explanation,
            "claims_breakdown": claims_breakdown,
            "mass_balance_result": mb_result,
            "evidence_bundle": bundle,
            "blockchain": {
                "network_label": blockchain_service.network_label,
                "chain_id": blockchain_service.chain_id,
                "is_anchored": is_anchored,
                "tx_hash": tx_hash,
                "evidence_commitment": bundle.bundle_keccak256_commitment,
                "block_number": block_number,
            },
            "certificate": certificate,
            "certificate_block_reason": certificate_block_reason,
            "ai_observation": ai_result,
            "ai_notice": ai_notice,
        }


custom_verification_service = CustomVerificationService()
