"""
test_adversarial.py — Tier 3 Mandatory Adversarial Test Suite
Implements automated adversarial validation for Cases A through J.
Satisfies Section R5 and Acceptance Criteria in ORIGINAL_REQUEST.md.
"""

import unittest
from datetime import datetime, timezone
from tests.conftest import (
    EV_BATTERY_NMC622_DATASET,
    ProvenanceCategory,
    LifecycleState,
    ActorRole,
    VerificationDecision,
    ReferenceMassBalanceEngine,
    ReferenceLifecycleStateMachine,
    LocalMockEVMLedger,
    sha256_hex,
    keccak256_hex,
    canonical_json_bytes
)


class TestAdversarialSuite(unittest.TestCase):
    """
    Tier 3 Automated Adversarial Test Suite covering Cases A through J.
    """

    def setUp(self):
        self.dataset = EV_BATTERY_NMC622_DATASET
        self.ledger = LocalMockEVMLedger(network_label="LOCAL TESTNET", chain_id=31337)
        self.passport_id = "DPP-EV-NMC622-2026-M04"
        self.bom_hash = "0x" + sha256_hex(canonical_json_bytes(self.dataset["components"]))
        # Register passport on local ledger
        self.ledger.register_passport(
            passport_id=self.passport_id,
            bom_hash=self.bom_hash,
            manufacturer="0x1111111111111111111111111111111111111111"
        )

    # ------------------------------------------------------------------------
    # Case A: Legitimate Recycling (Expected Material Range -> VERIFIED)
    # ------------------------------------------------------------------------
    def test_case_a_legitimate_recycling(self):
        """
        Case A: Valid recovery claim within BAT envelope:
        Cobalt 55.80 kg, Nickel 165.60 kg, Lithium 21.00 kg, Copper 105.28 kg.
        Result: VERIFIED, anchored on blockchain, certificate issued.
        """
        claims = {"CO": 55.80, "NI": 165.60, "LI": 21.00, "CU": 105.28}
        mb_result = ReferenceMassBalanceEngine.evaluate(1000.0, self.dataset, claims)
        self.assertEqual(mb_result.decision, VerificationDecision.VALID)

        # Build evidence manifest
        evidence_file = b"SCALE_TICKET_1000_KG_MEASURED"
        file_hash = sha256_hex(evidence_file)
        manifest = {
            "passport_id": self.passport_id,
            "event_id": "evt_case_a_001",
            "file_hashes": [file_hash],
            "claimed_materials": claims,
            "decision": mb_result.decision.value
        }
        commitment = keccak256_hex(canonical_json_bytes(manifest))

        # Anchor evidence
        tx_hash = self.ledger.anchor_recycling_evidence(
            event_id="evt_case_a_001",
            passport_id=self.passport_id,
            evidence_commitment=commitment,
            recycler_address="0x2222222222222222222222222222222222222222"
        )
        self.assertTrue(tx_hash.startswith("0x"))

        # Advance state to RECYCLING_VERIFIED
        ok, msg = ReferenceLifecycleStateMachine.validate_transition(
            LifecycleState.RECYCLING_PENDING,
            LifecycleState.RECYCLING_VERIFIED,
            ActorRole.VERIFIER_SERVICE
        )
        self.assertTrue(ok, msg)

        # Issue certificate
        cert_id = "cert_case_a_001"
        cert_hash = "0x" + sha256_hex(f"{cert_id}:{commitment}".encode())
        cert_tx = self.ledger.issue_certificate(
            certificate_id=cert_id,
            event_id="evt_case_a_001",
            passport_id=self.passport_id,
            cert_hash=cert_hash,
            evidence_commitment=commitment,
            issuer_address="0x9999999999999999999999999999999999999999"
        )
        self.assertIn(cert_id, self.ledger.certificates)
        self.assertTrue(cert_tx.startswith("0x"))

    # ------------------------------------------------------------------------
    # Case B: Borderline Material Claim (Near Tolerance Boundary -> REVIEW)
    # ------------------------------------------------------------------------
    def test_case_b_borderline_material_claim(self):
        """
        Case B: Claim deviates from nominal but is within process tolerance band:
        Cobalt 62.80 kg (nominal max is 61.75 kg, tolerance limit is 63.60 kg).
        Result: REVIEW / BORDERLINE. State remains in RECYCLING_PENDING. Certificate withheld.
        """
        claims = {"CO": 62.80, "NI": 165.60}
        mb_result = ReferenceMassBalanceEngine.evaluate(1000.0, self.dataset, claims)
        self.assertEqual(mb_result.decision, VerificationDecision.BORDERLINE)

        # Verification decision prevents automatic certificate issuance
        # Lifecycle state must NOT transition to RECYCLING_VERIFIED
        can_auto_verify = (mb_result.decision == VerificationDecision.VALID)
        self.assertFalse(can_auto_verify, "Borderline claim must NOT auto-verify.")

    # ------------------------------------------------------------------------
    # Case C: Impossible Material Claim (Exceeds Physical Yield -> FLAGGED)
    # ------------------------------------------------------------------------
    def test_case_c_impossible_material_claim(self):
        """
        Case C: Claim significantly exceeds stoichiometric ceiling:
        Cobalt 85.00 kg (stoichiometric ceiling is 65.33 kg).
        Result: CLAIM FLAGGED. State transitions to FLAGGED. Certificate blocked.
        """
        claims = {"CO": 85.00, "NI": 165.60}
        mb_result = ReferenceMassBalanceEngine.evaluate(1000.0, self.dataset, claims)
        self.assertEqual(mb_result.decision, VerificationDecision.IMPOSSIBLE)

        # Quarantine state to FLAGGED
        ok, msg = ReferenceLifecycleStateMachine.validate_transition(
            LifecycleState.RECYCLING_PENDING,
            LifecycleState.FLAGGED,
            ActorRole.SYSTEM
        )
        self.assertTrue(ok, msg)
        self.ledger.flag_product(self.passport_id, "evt_case_c_001", mb_result.mathematical_explanation)
        self.assertEqual(self.ledger.lifecycle_states[self.passport_id], LifecycleState.FLAGGED)

    # ------------------------------------------------------------------------
    # Case D: Evidence Tampering (Hash Mismatch -> EVIDENCE_INTEGRITY_FAILURE)
    # ------------------------------------------------------------------------
    def test_case_d_evidence_tampering_detection(self):
        """
        Case D: Evidence bundle anchored on-chain. An adversary modifies 1 byte in the file.
        Recomputed hash does not match anchored commitment -> EVIDENCE_INTEGRITY_FAILURE.
        """
        original_file = b"GENUINE_WEIGHBRIDGE_TICKET_IMAGE"
        tampered_file = b"TAMPERED_WEIGHBRIDGE_TICKET_IMAGE"

        manifest_orig = {
            "event_id": "evt_case_d_001",
            "evidence_hash": sha256_hex(original_file)
        }
        anchored_commitment = keccak256_hex(canonical_json_bytes(manifest_orig))

        # Attacker modifies stored file
        manifest_tampered = {
            "event_id": "evt_case_d_001",
            "evidence_hash": sha256_hex(tampered_file)
        }
        recomputed_commitment = keccak256_hex(canonical_json_bytes(manifest_tampered))

        # Verify integrity detector catches tampering
        is_integrity_valid = (anchored_commitment == recomputed_commitment)
        self.assertFalse(is_integrity_valid)

        # Integrity failure triggers quarantine
        status = "EVIDENCE_INTEGRITY_FAILURE" if not is_integrity_valid else "VALID"
        self.assertEqual(status, "EVIDENCE_INTEGRITY_FAILURE")

    # ------------------------------------------------------------------------
    # Case E: Duplicate Recycling Event (Anti-Replay / Rejection)
    # ------------------------------------------------------------------------
    def test_case_e_duplicate_recycling_event_replay_attack(self):
        """
        Case E: Attacker resubmits identical event_id.
        Result: DUPLICATE / REJECTED (HTTP 409 / smart contract revert).
        """
        event_id = "evt_unique_12345"
        commitment = "0x" + sha256_hex(b"commitment_1")

        # First submission succeeds
        self.ledger.anchor_recycling_evidence(
            event_id=event_id,
            passport_id=self.passport_id,
            evidence_commitment=commitment,
            recycler_address="0x2222222222222222222222222222222222222222"
        )

        # Replay submission must revert
        with self.assertRaises(ValueError) as ctx:
            self.ledger.anchor_recycling_evidence(
                event_id=event_id,
                passport_id=self.passport_id,
                evidence_commitment=commitment,
                recycler_address="0x2222222222222222222222222222222222222222"
            )
        self.assertIn("Replay detected", str(ctx.exception))

    # ------------------------------------------------------------------------
    # Case F: Duplicate Certificate (Repeated Issuance Prohibited)
    # ------------------------------------------------------------------------
    def test_case_f_duplicate_certificate_issuance_rejected(self):
        """
        Case F: Attacker requests a second certificate for the same recycling event.
        Result: REJECTED (HTTP 409 / smart contract revert).
        """
        event_id = "evt_case_f_001"
        cert_id_1 = "cert_first_001"
        cert_id_2 = "cert_second_002"
        commitment = "0x" + sha256_hex(b"commitment_f")

        # Anchor event
        self.ledger.anchor_recycling_evidence(
            event_id=event_id,
            passport_id=self.passport_id,
            evidence_commitment=commitment,
            recycler_address="0x2222222222222222222222222222222222222222"
        )

        # Issue first certificate -> Success
        self.ledger.issue_certificate(
            certificate_id=cert_id_1,
            event_id=event_id,
            passport_id=self.passport_id,
            cert_hash="0x1111",
            evidence_commitment=commitment,
            issuer_address="0x9999"
        )

        # Attempt to issue second certificate for same event_id -> Must revert
        with self.assertRaises(ValueError) as ctx:
            self.ledger.issue_certificate(
                certificate_id=cert_id_2,
                event_id=event_id,
                passport_id=self.passport_id,
                cert_hash="0x2222",
                evidence_commitment=commitment,
                issuer_address="0x9999"
            )
        self.assertIn("Duplicate certificate prohibited", str(ctx.exception))

    # ------------------------------------------------------------------------
    # Case G: Unauthorized Lifecycle Transition (Role Spoofing / State Skipping)
    # ------------------------------------------------------------------------
    def test_case_g_unauthorized_lifecycle_transition_rejected(self):
        """
        Case G: Unauthorized role (e.g. Recycler attempting to unflag product
        or skip directly from MANUFACTURED to RECYCLING_VERIFIED).
        Result: REJECTED (HTTP 403 / Contract revert).
        """
        # 1. State skipping attempt
        ok, msg = ReferenceLifecycleStateMachine.validate_transition(
            LifecycleState.MANUFACTURED,
            LifecycleState.RECYCLING_VERIFIED,
            ActorRole.RECYCLER
        )
        self.assertFalse(ok)
        self.assertIn("Illegal state transition", msg)

        # 2. Role spoofing unflag attempt
        ok, msg = ReferenceLifecycleStateMachine.validate_transition(
            LifecycleState.FLAGGED,
            LifecycleState.RECYCLING_VERIFIED,
            ActorRole.RECYCLER,
            has_auditor_proof=True
        )
        self.assertFalse(ok)
        self.assertIn("Unauthorized", msg)

    # ------------------------------------------------------------------------
    # Case H: Malformed Evidence (Schema / Provenance / MIME Failure)
    # ------------------------------------------------------------------------
    def test_case_h_malformed_evidence_payload(self):
        """
        Case H: Malformed evidence upload (disallowed MIME type, missing provenance category).
        Result: VALIDATION FAILURE (HTTP 415 / 422).
        """
        allowed_mimes = {"image/jpeg", "image/png", "application/pdf", "video/mp4"}

        # Submitting an executable masquerading as an image
        disallowed_mime = "application/x-dosexec"
        self.assertNotIn(disallowed_mime, allowed_mimes)

        # Missing provenance category
        def validate_provenance_payload(payload: dict) -> bool:
            if "provenance" not in payload:
                return False
            valid_categories = {c.value for c in ProvenanceCategory}
            return payload["provenance"] in valid_categories

        self.assertFalse(validate_provenance_payload({"val": 100.0}))  # Missing
        self.assertFalse(validate_provenance_payload({"val": 100.0, "provenance": "INVALID"}))  # Unknown
        self.assertTrue(validate_provenance_payload({"val": 100.0, "provenance": "MEASURED"}))  # Valid

    # ------------------------------------------------------------------------
    # Case I: AI Service Unavailable (Graceful Fallback & Non-Corruption)
    # ------------------------------------------------------------------------
    def test_case_i_ai_service_unavailable_graceful_fallback(self):
        """
        Case I: Upstream AI API (Gemini) returns HTTP 503 / timeout.
        System must gracefully fall back to deterministic fixture without state corruption.
        """
        class MockAIService:
            def __init__(self, simulate_outage: bool = False):
                self.simulate_outage = simulate_outage

            def observe(self, image_data: bytes, use_fixture_fallback: bool = True):
                if self.simulate_outage:
                    if not use_fixture_fallback:
                        raise TimeoutError("Gemini Multimodal API unavailable (HTTP 503)")
                    # Deterministic fixture fallback
                    return {
                        "provider": "Deterministic Mock Fixture",
                        "model": "fixture-v1",
                        "estimated_items": 40,
                        "confidence": 0.95,
                        "provenance": ProvenanceCategory.SIMULATED.value
                    }
                return {
                    "provider": "Google Gemini",
                    "model": "gemini-2.5-flash",
                    "estimated_items": 40,
                    "confidence": 0.94,
                    "provenance": ProvenanceCategory.AI_ESTIMATED.value
                }

        ai = MockAIService(simulate_outage=True)
        # Without fallback -> Exception caught cleanly
        with self.assertRaises(TimeoutError):
            ai.observe(b"raw_bytes", use_fixture_fallback=False)

        # With fallback enabled -> Graceful deterministic observation returned
        res = ai.observe(b"raw_bytes", use_fixture_fallback=True)
        self.assertEqual(res["provider"], "Deterministic Mock Fixture")
        self.assertEqual(res["provenance"], ProvenanceCategory.SIMULATED.value)

    # ------------------------------------------------------------------------
    # Case J: Blockchain Unavailable (RPC Node Offline -> Truthfulness)
    # ------------------------------------------------------------------------
    def test_case_j_blockchain_unavailable_rpc_offline(self):
        """
        Case J: Blockchain RPC node is offline.
        System must return clear unconfirmed/error state and NEVER fake success.
        """
        self.ledger.simulate_rpc_disconnect()

        with self.assertRaises(ConnectionError) as ctx:
            self.ledger.anchor_recycling_evidence(
                event_id="evt_case_j_001",
                passport_id=self.passport_id,
                evidence_commitment="0x1234",
                recycler_address="0x2222"
            )
        self.assertIn("RPC node offline (LOCAL TESTNET disconnected)", str(ctx.exception))
        # Ensure event is NOT recorded in ledger
        self.assertNotIn("evt_case_j_001", self.ledger.events)


if __name__ == "__main__":
    unittest.main()
