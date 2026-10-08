#!/usr/bin/env python3
"""
RE:TRACE Phase 1 Gate Schema & Domain Logic Validator.

Validates canonical schemas (DPP, MaterialComposition, RecyclingEvent, EvidenceBundle,
ProofOfRecyclingCertificate), deterministic mass-balance evaluation engine, RFC 8785
canonical manifest hashing, and lifecycle state transition guards against reference datasets.
"""

from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path

# Add project root and venv site-packages to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
VENV_SITE = WORKSPACE_ROOT / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
if VENV_SITE.is_dir() and str(VENV_SITE) not in sys.path:
    sys.path.insert(0, str(VENV_SITE))

from shared.schemas.provenance import ProvenanceCategory, ProvenanceRecord
from shared.schemas.material import MaterialComponent, MaterialComposition
from shared.schemas.dpp import DigitalProductPassport
from shared.schemas.recycling_event import ClaimedMaterial, RecyclingEvent
from shared.schemas.evidence_bundle import (
    EvidenceFileRecord,
    AIInferenceObservation,
    MassBalanceVerificationResult,
    EvidenceBundle,
)
from shared.schemas.por_certificate import (
    VerifiedMaterialQuantity,
    ProofOfRecyclingCertificate,
)
from shared.domain.lifecycle import (
    LifecycleState,
    AuthorizedRole,
    validate_transition,
)
from shared.domain.mass_balance import (
    MassBalanceOutcome,
    evaluate_mass_balance,
)
from shared.domain.evidence_hasher import (
    canonicalize_json,
    hash_bytes_sha256,
    keccak256,
    compute_evidence_bundle_commitment,
)
from shared.fixtures.reference_materials import (
    EV_BATTERY_NMC_622_DPP,
    EV_BATTERY_NMC_622_COMPOSITION,
    SMARTPHONE_LCO_DPP,
    SMARTPHONE_LCO_COMPOSITION,
)


def log_test(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    if details:
        print(f"       -> {details}")
    if not passed:
        raise AssertionError(f"Test failed: {name} - {details}")


def test_dpp_and_material_schemas():
    print("\n--- 1. Testing Digital Product Passport & Material Schemas ---")

    # 1.1 Valid EV Battery DPP
    dpp = EV_BATTERY_NMC_622_DPP
    log_test("Valid NMC 622 DPP instantiation", dpp.passport_id == "dpp-ev-nmc622-2026-m04")
    log_test(
        "NMC 622 Material Composition percentage sum check",
        abs(sum(c.percentage for c in dpp.material_composition.components) - 100.0) < 1e-4,
    )

    # 1.2 Valid Smartphone DPP
    phone_dpp = SMARTPHONE_LCO_DPP
    log_test("Valid Smartphone LCO DPP instantiation", phone_dpp.product_category == "CONSUMER_BATTERY")

    # 1.3 Invalid Material Composition (Sum != 100%)
    invalid_components = [
        MaterialComponent(
            material_name="Lithium",
            mass_kg=1.0,
            percentage=30.0,
            provenance=ProvenanceCategory.REFERENCE_ASSUMED,
        ),
        MaterialComponent(
            material_name="Cobalt",
            mass_kg=2.0,
            percentage=40.0,
            provenance=ProvenanceCategory.REFERENCE_ASSUMED,
        ),
    ]
    sum_failed = False
    try:
        MaterialComposition(components=invalid_components, total_mass_kg=3.0)
    except ValueError as e:
        sum_failed = True
        log_test("Invalid material percentage sum rejected (70% != 100%)", True, str(e))
    if not sum_failed:
        log_test("Invalid material percentage sum rejected", False, "Should have raised ValueError")


def test_recycling_event_schema():
    print("\n--- 2. Testing Recycling Event Schema ---")

    claimed = [
        ClaimedMaterial(
            material_name="Nickel",
            claimed_mass_kg=165.60,
            purity_pct=99.2,
            provenance=ProvenanceCategory.MEASURED,
        ),
        ClaimedMaterial(
            material_name="Cobalt",
            claimed_mass_kg=55.80,
            purity_pct=98.8,
            provenance=ProvenanceCategory.MEASURED,
        ),
        ClaimedMaterial(
            material_name="Lithium",
            claimed_mass_kg=21.00,
            purity_pct=97.5,
            provenance=ProvenanceCategory.MEASURED,
        ),
        ClaimedMaterial(
            material_name="Copper",
            claimed_mass_kg=105.28,
            purity_pct=99.5,
            provenance=ProvenanceCategory.MEASURED,
        ),
    ]

    event = RecyclingEvent(
        event_id="evt-recycling-nmc622-001",
        passport_id=EV_BATTERY_NMC_622_DPP.passport_id,
        facility_id="facility-eu-berlin-04",
        operator_id="operator-4821",
        intake_gross_mass_kg=1000.0,  # 40 modules @ 25 kg
        intake_mass_provenance=ProvenanceCategory.MEASURED,
        claimed_materials=claimed,
        evidence_file_ids=["file-photo-intake-001", "file-weighbridge-ticket-002"],
        processing_method="HYDROMETALLURGICAL",
        timestamp=datetime.now(timezone.utc),
        status="SUBMITTED",
    )
    log_test("Valid RecyclingEvent instantiation", event.event_id == "evt-recycling-nmc622-001")


def test_mass_balance_engine():
    print("\n--- 3. Testing Deterministic Mass-Balance Engine ---")
    comp = EV_BATTERY_NMC_622_COMPOSITION
    intake_mass = 1000.0  # kg

    # 3.1 Case A: Legitimate Claim -> VALID
    legit_claims = [
        ClaimedMaterial(material_name="Nickel", claimed_mass_kg=165.60),  # exp: 165.60 kg
        ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=55.80),    # exp: 55.80 kg
        ClaimedMaterial(material_name="Lithium", claimed_mass_kg=21.00),   # exp: 21.00 kg
        ClaimedMaterial(material_name="Copper", claimed_mass_kg=105.28),   # exp: 105.28 kg
    ]
    res_legit = evaluate_mass_balance(intake_mass, comp, legit_claims)
    log_test(
        "Case A: Legitimate recycling claim evaluated as VALID",
        res_legit.decision == MassBalanceOutcome.VALID.value,
        res_legit.mathematical_explanation[:90] + "...",
    )

    # 3.2 Case B: Borderline Claim -> BORDERLINE
    # Cobalt exp: 55.80 kg, tau=5% -> upper: 58.59 kg. Claim 59.50 kg is in [58.59, 60.30]
    borderline_claims = [
        ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=59.50),
    ]
    res_borderline = evaluate_mass_balance(intake_mass, comp, borderline_claims)
    log_test(
        "Case B: Borderline claim evaluated as BORDERLINE",
        res_borderline.decision == MassBalanceOutcome.BORDERLINE.value,
        res_borderline.mathematical_explanation[:90] + "...",
    )

    # 3.3 Case C: Impossible Claim (Exceeds Stoichiometric Ceiling) -> IMPOSSIBLE
    # Cobalt in 1000kg batch is 60.00 kg total. Claim 95.00 kg violates chemistry!
    impossible_claims = [
        ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=95.00),
    ]
    res_impossible = evaluate_mass_balance(intake_mass, comp, impossible_claims)
    log_test(
        "Case C: Impossible claim (exceeds theoretical max) evaluated as IMPOSSIBLE",
        res_impossible.decision == MassBalanceOutcome.IMPOSSIBLE.value,
        res_impossible.mathematical_explanation[:90] + "...",
    )

    # 3.4 Case D: Gross Conservation of Mass Violation -> IMPOSSIBLE
    gross_impossible = [
        ClaimedMaterial(material_name="Nickel", claimed_mass_kg=600.0),
        ClaimedMaterial(material_name="Aluminum", claimed_mass_kg=500.0),
    ]  # Total claimed: 1100 kg > 1000 kg intake!
    res_gross = evaluate_mass_balance(intake_mass, comp, gross_impossible)
    log_test(
        "Case D: Total claimed mass > intake mass evaluated as IMPOSSIBLE",
        res_gross.decision == MassBalanceOutcome.IMPOSSIBLE.value,
        res_gross.mathematical_explanation[:90] + "...",
    )


def test_evidence_hashing_and_bundle():
    print("\n--- 4. Testing RFC 8785 Canonical Hasher & Evidence Bundle ---")

    # Raw file record
    sample_file_bytes = b"RETRACE_EVIDENCE_SAMPLE_PHOTO_WEIGHBRIDGE_2026_TEST"
    file_sha256 = hash_bytes_sha256(sample_file_bytes)
    file_record = EvidenceFileRecord(
        file_id="file-weighbridge-001",
        filename="weighbridge_receipt_1000kg.jpg",
        mime_type="image/jpeg",
        file_size_bytes=len(sample_file_bytes),
        sha256_hash=file_sha256,
        provenance=ProvenanceCategory.MEASURED,
    )
    log_test("EvidenceFileRecord SHA-256 computed", len(file_sha256) == 64)

    # AI Observation
    ai_obs = AIInferenceObservation(
        model_provider="Deterministic Mock Fixture",
        model_version="fixture-v1",
        inference_timestamp=datetime.now(timezone.utc),
        detected_objects=["EV_Battery_Module", "NorthVolt_Casing", "Barcode_Tag"],
        estimated_materials={"Nickel": 170.0, "Cobalt": 58.0, "Copper": 108.0},
        confidence_scores={"classification": 0.98, "mass_prior": 0.92},
        provenance=ProvenanceCategory.AI_ESTIMATED,
    )

    # Mass balance result
    comp = EV_BATTERY_NMC_622_COMPOSITION
    claims = [
        ClaimedMaterial(material_name="Nickel", claimed_mass_kg=165.60),
        ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=55.80),
    ]
    mb_result = evaluate_mass_balance(1000.0, comp, claims)

    # Manifest for commitment
    manifest_payload = {
        "event_id": "evt-recycling-nmc622-001",
        "passport_id": EV_BATTERY_NMC_622_DPP.passport_id,
        "files": [file_record.model_dump(mode="python")],
        "ai_observation": ai_obs.model_dump(mode="python"),
        "mass_balance": mb_result.model_dump(mode="python"),
    }

    manifest_sha256, keccak_commitment = compute_evidence_bundle_commitment(manifest_payload)
    log_test("Canonical manifest SHA-256 calculated", len(manifest_sha256) == 64)
    log_test("EVM keccak256 commitment calculated", keccak_commitment.startswith("0x") and len(keccak_commitment) == 66)

    # Test tampering sensitivity
    tampered_manifest = dict(manifest_payload)
    tampered_manifest["tamper_test"] = "unauthorized_modification"
    tampered_sha, tampered_keccak = compute_evidence_bundle_commitment(tampered_manifest)
    log_test(
        "Cryptographic tampering sensitivity confirmed (hash mismatch on mutation)",
        manifest_sha256 != tampered_sha and keccak_commitment != tampered_keccak,
    )

    # Complete EvidenceBundle instantiation
    bundle = EvidenceBundle(
        bundle_id="bundle-nmc622-001",
        event_id="evt-recycling-nmc622-001",
        passport_id=EV_BATTERY_NMC_622_DPP.passport_id,
        evidence_files=[file_record],
        ai_observation=ai_obs,
        mass_balance_result=mb_result,
        canonical_manifest_sha256=manifest_sha256,
        bundle_keccak256_commitment=keccak_commitment,
        blockchain_tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        blockchain_network="LOCAL TESTNET",
        created_at=datetime.now(timezone.utc),
    )
    log_test("EvidenceBundle validated successfully", bundle.bundle_id == "bundle-nmc622-001")


def test_certificate_schema():
    print("\n--- 5. Testing Proof-of-Recycling Certificate Schema ---")
    verified_quantities = [
        VerifiedMaterialQuantity(
            material_name="Nickel",
            recovered_mass_kg=165.60,
            purity_pct=99.2,
            recovery_yield_pct=92.0,
        ),
        VerifiedMaterialQuantity(
            material_name="Cobalt",
            recovered_mass_kg=55.80,
            purity_pct=98.8,
            recovery_yield_pct=93.0,
        ),
    ]

    cert = ProofOfRecyclingCertificate(
        certificate_id="cert-por-2026-0001",
        passport_id=EV_BATTERY_NMC_622_DPP.passport_id,
        event_id="evt-recycling-nmc622-001",
        facility_id="facility-eu-berlin-04",
        verified_material_quantities=verified_quantities,
        verification_result="VERIFIED",
        verification_confidence=0.96,
        evidence_commitment="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        blockchain_transaction_reference="0xdeadbeef1234567890deadbeef1234567890deadbeef1234567890deadbeef",
        blockchain_network="LOCAL TESTNET",
        issued_at=datetime.now(timezone.utc),
        certificate_hash=hash_bytes_sha256(b"SAMPLE_CERTIFICATE_CANONICAL_PAYLOAD"),
    )
    log_test("ProofOfRecyclingCertificate validated", cert.certificate_id == "cert-por-2026-0001")


def test_lifecycle_state_machine():
    print("\n--- 6. Testing Lifecycle State Machine Transition Guards ---")

    # 6.1 Valid linear progression
    t1 = validate_transition(
        LifecycleState.MANUFACTURED, LifecycleState.IN_USE, AuthorizedRole.LOGISTICS
    )
    log_test("MANUFACTURED -> IN_USE allowed for LOGISTICS", t1.is_valid)

    t2 = validate_transition(
        LifecycleState.IN_USE, LifecycleState.RETURNED, AuthorizedRole.COLLECTION_AGENT
    )
    log_test("IN_USE -> RETURNED allowed for COLLECTION_AGENT", t2.is_valid)

    t3 = validate_transition(
        LifecycleState.RETURNED, LifecycleState.RECYCLING_PENDING, AuthorizedRole.RECYCLER
    )
    log_test("RETURNED -> RECYCLING_PENDING allowed for RECYCLER", t3.is_valid)

    # Guard condition test: RECYCLING_PENDING -> RECYCLING_VERIFIED
    t4_bad_guard = validate_transition(
        LifecycleState.RECYCLING_PENDING,
        LifecycleState.RECYCLING_VERIFIED,
        AuthorizedRole.VERIFIER_SERVICE,
        guard_context={"mass_balance_decision": "BORDERLINE"},
    )
    log_test(
        "RECYCLING_PENDING -> RECYCLING_VERIFIED blocked when mass_balance != VALID",
        not t4_bad_guard.is_valid,
        t4_bad_guard.message,
    )

    t4_good_guard = validate_transition(
        LifecycleState.RECYCLING_PENDING,
        LifecycleState.RECYCLING_VERIFIED,
        AuthorizedRole.VERIFIER_SERVICE,
        guard_context={
            "mass_balance_decision": "VALID",
            "evidence_commitment": "0x1234",
        },
    )
    log_test("RECYCLING_PENDING -> RECYCLING_VERIFIED passed when guard conditions met", t4_good_guard.is_valid)

    # 6.2 Illegal state skip (MANUFACTURED -> RECYCLING_VERIFIED)
    t_skip = validate_transition(
        LifecycleState.MANUFACTURED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.SYSTEM
    )
    log_test("Illegal state hop MANUFACTURED -> RECYCLING_VERIFIED blocked", not t_skip.is_valid, t_skip.message)

    # 6.3 Anti-replay self transition
    t_replay = validate_transition(
        LifecycleState.RECYCLING_VERIFIED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.SYSTEM
    )
    log_test("Anti-replay self-loop blocked", not t_replay.is_valid, t_replay.message)

    # 6.4 Quarantine and Auditor-only flag resolution
    t_flag = validate_transition(
        LifecycleState.RECYCLING_PENDING, LifecycleState.FLAGGED, AuthorizedRole.VERIFIER_SERVICE
    )
    log_test("RECYCLING_PENDING -> FLAGGED allowed for VERIFIER_SERVICE", t_flag.is_valid)

    # Recycler cannot unflag!
    t_unflag_recycler = validate_transition(
        LifecycleState.FLAGGED,
        LifecycleState.RECYCLING_VERIFIED,
        AuthorizedRole.RECYCLER,
        guard_context={"auditor_resolution_notes": "Recycler claims everything is fine."},
    )
    log_test("Recycler prohibited from unflagging quarantined product", not t_unflag_recycler.is_valid)

    # Auditor CAN unflag with resolution notes
    t_unflag_auditor = validate_transition(
        LifecycleState.FLAGGED,
        LifecycleState.RECYCLING_VERIFIED,
        AuthorizedRole.AUDITOR,
        guard_context={"auditor_resolution_notes": "Official audit completed. Lab titration logs verified."},
    )
    log_test("Auditor authorized to unflag with documented notes", t_unflag_auditor.is_valid)


def main():
    print("================================================================")
    print("  RE:TRACE Phase 1 Gate: Canonical Schema & Logic Validator")
    print("================================================================")

    test_dpp_and_material_schemas()
    test_recycling_event_schema()
    test_mass_balance_engine()
    test_evidence_hashing_and_bundle()
    test_certificate_schema()
    test_lifecycle_state_machine()

    print("\n================================================================")
    print("  ALL CANONICAL SCHEMAS & DOMAIN ENGINES VALIDATED SUCCESSFULLY! ")
    print("================================================================")


if __name__ == "__main__":
    main()
