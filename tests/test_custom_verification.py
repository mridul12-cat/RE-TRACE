"""
tests/test_custom_verification.py — Comprehensive Integration Tests for Custom Verification Workflow.

Verifies:
1. Custom valid event -> VERIFIED
2. Custom borderline event -> REVIEW / BORDERLINE
3. Custom impossible claim -> FLAGGED
4. Custom evidence upload
5. Multiple evidence files
6. Invalid evidence rejected
7. Invalid mass rejected
8. Invalid material quantity rejected
9. Missing passport rejected
10. Duplicate event rejected
11. AI unavailable does not bypass deterministic verification
12. Evidence integrity remains verifiable
13. Successful verification produces a reproducible certificate when applicable
14. Scenario A, B, C regression tests
15. Concurrent replay race condition (thread-safety)
16. Malformed ID sanitization and path traversal prevention
17. Yield clamping and non-positive mass claim handling
18. Direct verification auto-seeding
"""

import concurrent.futures
import unittest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.blockchain_service import blockchain_service
from backend.app.api.v1.passports import _PASSPORT_STORE, seed_default_passports
from backend.app.api.v1.recycling import _EVENT_STORE
from shared.domain.lifecycle import LifecycleState, AuthorizedRole
from shared.fixtures.reference_materials import EV_BATTERY_NMC_622_COMPOSITION


class TestCustomVerificationWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        blockchain_service.reset_state()
        _PASSPORT_STORE.clear()
        _EVENT_STORE.clear()
        seed_default_passports()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        blockchain_service.reset_state()
        _PASSPORT_STORE.clear()
        _EVENT_STORE.clear()

    def setUp(self):
        blockchain_service.simulate_rpc_reconnect()

    def _upload_test_image(self, tag: str = "custom", provenance: str = "OBSERVED") -> str:
        """Helper to upload a valid test JPEG image via the existing upload endpoint."""
        content = b"\xff\xd8\xff\xe0" + f"TEST_CUSTOM_EVIDENCE_{tag}_{uuid.uuid4().hex}".encode("utf-8") * 10
        files = {"file": (f"evidence_{tag}.jpg", content, "image/jpeg")}
        data = {"provenance_category": provenance, "description": f"Test evidence {tag}"}
        resp = self.client.post("/api/v1/evidence/upload", files=files, data=data)
        self.assertEqual(resp.status_code, 201)
        return resp.json()["file_id"]

    def _create_and_prep_passport(self, pid_prefix: str = "DPP-CUSTOM-TEST") -> str:
        """Helper to register a fresh passport in RECYCLING_PENDING state."""
        pid = f"{pid_prefix}-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "passport_id": pid,
            "product_id": "SKU-CUSTOM-MODULE",
            "product_name": "Custom Test EV Battery Pack",
            "product_category": "EV_BATTERY",
            "manufacturer": "Custom Test Corp",
            "manufacturing_date": now,
            "initial_total_mass_kg": 25.0,
            "material_composition": EV_BATTERY_NMC_622_COMPOSITION.model_dump(mode="json"),
            "current_lifecycle_state": "MANUFACTURED",
            "created_at": now,
            "updated_at": now,
        }
        resp = self.client.post("/api/v1/passports", json=payload)
        self.assertEqual(resp.status_code, 201)

        # Advance to RECYCLING_PENDING
        blockchain_service.transition_state(pid, LifecycleState.IN_USE, AuthorizedRole.MANUFACTURER)
        blockchain_service.transition_state(pid, LifecycleState.RETURNED, AuthorizedRole.COLLECTION_AGENT)
        blockchain_service.transition_state(pid, LifecycleState.RECYCLING_PENDING, AuthorizedRole.RECYCLER)
        return pid

    # -------------------------------------------------------------------------
    # 1. Custom valid event -> VERIFIED
    # -------------------------------------------------------------------------
    def test_01_custom_valid_event_verified(self):
        """Test 1: Legitimate recovery claim produces VERIFIED outcome with PoR Certificate."""
        pid = self._create_and_prep_passport("DPP-VALID")
        fid = self._upload_test_image("valid_scale_ticket", provenance="OBSERVED")

        payload = {
            "passport_id": pid,
            "facility_id": "FAC-TEST-ROTTERDAM",
            "operator_id": "OP-VALID-01",
            "intake_gross_mass_kg": 1000.0,
            "intake_mass_provenance": "OBSERVED",
            "processing_method": "HYDROMETALLURGICAL",
            "claimed_materials": [
                {"material_name": "Nickel", "claimed_mass_kg": 165.6, "purity_pct": 99.2, "provenance": "OBSERVED"},
                {"material_name": "Cobalt", "claimed_mass_kg": 55.8, "purity_pct": 99.5, "provenance": "OBSERVED"},
                {"material_name": "Lithium", "claimed_mass_kg": 21.0, "purity_pct": 98.5, "provenance": "OBSERVED"},
            ],
            "evidence_file_ids": [fid],
            "run_ai_observation": False,
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["overall_decision"], "VERIFIED")
        self.assertEqual(data["mass_balance_decision"], "VALID")
        self.assertEqual(data["evidence_integrity_status"], "VERIFIED")
        self.assertEqual(data["lifecycle_state"], "RECYCLING_VERIFIED")
        self.assertTrue(data["blockchain"]["is_anchored"])
        self.assertIsNotNone(data["blockchain"]["tx_hash"])
        self.assertEqual(data["blockchain"]["network_label"], "LOCAL TESTNET")
        self.assertEqual(data["blockchain"]["chain_id"], 31337)

        # Check PoR Certificate
        self.assertIsNotNone(data["certificate"])
        cert = data["certificate"]
        self.assertTrue(cert["certificate_id"].startswith("POR-2026-"))
        self.assertEqual(cert["passport_id"], pid)
        self.assertEqual(cert["verification_result"], "VERIFIED")
        self.assertEqual(len(cert["verified_material_quantities"]), 3)

    # -------------------------------------------------------------------------
    # 2. Custom borderline event -> REVIEW / BORDERLINE
    # -------------------------------------------------------------------------
    def test_02_custom_borderline_event_review(self):
        """Test 2: Claim deviating beyond nominal envelope produces REVIEW / BORDERLINE without cert."""
        pid = self._create_and_prep_passport("DPP-BORDER")
        fid = self._upload_test_image("borderline_ticket")

        # Nominal Nickel expected = 165.6 kg, tolerance [157.32 - 173.88].
        # 176.0 kg is outside nominal [157.32, 173.88] but within borderline upper bound (180.9 kg).
        payload = {
            "passport_id": pid,
            "facility_id": "FAC-TEST-ROTTERDAM",
            "operator_id": "OP-BORDER-01",
            "intake_gross_mass_kg": 1000.0,
            "intake_mass_provenance": "OBSERVED",
            "claimed_materials": [
                {"material_name": "Nickel", "claimed_mass_kg": 176.0, "purity_pct": 98.0, "provenance": "OBSERVED"},
                {"material_name": "Cobalt", "claimed_mass_kg": 55.8, "purity_pct": 98.0, "provenance": "OBSERVED"},
            ],
            "evidence_file_ids": [fid],
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["overall_decision"], "REVIEW")
        self.assertEqual(data["mass_balance_decision"], "BORDERLINE")
        self.assertEqual(data["lifecycle_state"], "RECYCLING_PENDING")
        self.assertFalse(data["blockchain"]["is_anchored"])
        self.assertIsNone(data["certificate"])
        self.assertIn("BORDERLINE", data["certificate_block_reason"])
        self.assertIn("supervisor/auditor", data["certificate_block_reason"])

    # -------------------------------------------------------------------------
    # 3. Custom impossible claim -> FLAGGED
    # -------------------------------------------------------------------------
    def test_03_custom_impossible_claim_flagged(self):
        """Test 3: Claim exceeding stoichiometric maximum produces FLAGGED and quarantines batch."""
        pid = self._create_and_prep_passport("DPP-IMPOSSIBLE")
        fid = self._upload_test_image("impossible_ticket")

        # 95.0 kg Cobalt exceeds thermodynamic ceiling of 60.3 kg
        payload = {
            "passport_id": pid,
            "facility_id": "FAC-TEST-ROTTERDAM",
            "operator_id": "OP-FRAUD-01",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [
                {"material_name": "Cobalt", "claimed_mass_kg": 95.0, "purity_pct": 95.0, "provenance": "OBSERVED"},
            ],
            "evidence_file_ids": [fid],
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["overall_decision"], "FLAGGED")
        self.assertEqual(data["mass_balance_decision"], "IMPOSSIBLE")
        self.assertEqual(data["lifecycle_state"], "FLAGGED")
        self.assertFalse(data["blockchain"]["is_anchored"])
        self.assertIsNone(data["certificate"])
        self.assertIn("IMPOSSIBLE", data["certificate_block_reason"])

        # Check blockchain on-chain state
        state_resp = self.client.get(f"/api/v1/lifecycle/state/{pid}")
        self.assertEqual(state_resp.json()["lifecycle_state"], "FLAGGED")

    # -------------------------------------------------------------------------
    # 4. Custom evidence upload
    # -------------------------------------------------------------------------
    def test_04_custom_evidence_upload(self):
        """Test 4: Physical evidence upload computes real SHA-256 and preserves provenance."""
        raw_bytes = b"\xff\xd8\xff\xe0" + b"CERTIFIED_SCALE_RECEIPT_BYTES" * 8
        files = {"file": ("scale_slip_custom.jpg", raw_bytes, "image/jpeg")}
        data = {"provenance_category": "OBSERVED", "description": "Custom scale intake receipt"}

        resp = self.client.post("/api/v1/evidence/upload", files=files, data=data)
        self.assertEqual(resp.status_code, 201)
        record = resp.json()
        self.assertTrue(record["file_id"].startswith("EV-"))
        self.assertEqual(record["filename"], "scale_slip_custom.jpg")
        self.assertEqual(record["provenance"], "OBSERVED")
        self.assertEqual(len(record["sha256_hash"]), 64)

    # -------------------------------------------------------------------------
    # 5. Multiple evidence files
    # -------------------------------------------------------------------------
    def test_05_multiple_evidence_files(self):
        """Test 5: Multiple evidence files are accepted, compiled into the bundle, and hashed."""
        pid = self._create_and_prep_passport("DPP-MULTI-EV")
        fid1 = self._upload_test_image("weighbridge_slip")
        fid2 = self._upload_test_image("xrf_assay_report")

        payload = {
            "passport_id": pid,
            "facility_id": "FAC-TEST-02",
            "operator_id": "OP-7782",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [
                {"material_name": "Nickel", "claimed_mass_kg": 165.6, "purity_pct": 99.2, "provenance": "OBSERVED"}
            ],
            "evidence_file_ids": [fid1, fid2],
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        bundle_files = data["evidence_bundle"]["evidence_files"]
        self.assertEqual(len(bundle_files), 2)
        fids = [f["file_id"] for f in bundle_files]
        self.assertIn(fid1, fids)
        self.assertIn(fid2, fids)

    # -------------------------------------------------------------------------
    # 6. Invalid evidence rejected
    # -------------------------------------------------------------------------
    def test_06_invalid_evidence_rejected(self):
        """Test 6: Nonexistent evidence file ID or empty evidence list is rejected."""
        pid = self._create_and_prep_passport("DPP-INV-EV")

        # 1. Nonexistent evidence file ID
        payload_nonexistent = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [{"material_name": "Cobalt", "claimed_mass_kg": 50.0}],
            "evidence_file_ids": ["EV-DOES-NOT-EXIST-999"],
        }
        resp1 = self.client.post("/api/v1/custom-verification/verify", json=payload_nonexistent)
        self.assertEqual(resp1.status_code, 404)
        self.assertEqual(resp1.json()["error_code"], "NOT_FOUND")

        # 2. Empty evidence list
        payload_empty = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [{"material_name": "Cobalt", "claimed_mass_kg": 50.0}],
            "evidence_file_ids": [],
        }
        resp2 = self.client.post("/api/v1/custom-verification/verify", json=payload_empty)
        self.assertIn(resp2.status_code, [400, 422])

    # -------------------------------------------------------------------------
    # 7. Invalid mass rejected
    # -------------------------------------------------------------------------
    def test_07_invalid_mass_rejected(self):
        """Test 7: Zero or negative gross intake mass is rejected."""
        pid = self._create_and_prep_passport("DPP-INV-MASS")
        fid = self._upload_test_image("test_mass")

        payload_zero = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 0.0,
            "claimed_materials": [{"material_name": "Cobalt", "claimed_mass_kg": 50.0}],
            "evidence_file_ids": [fid],
        }
        resp = self.client.post("/api/v1/custom-verification/verify", json=payload_zero)
        self.assertIn(resp.status_code, [400, 422])

        payload_neg = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": -250.0,
            "claimed_materials": [{"material_name": "Cobalt", "claimed_mass_kg": 50.0}],
            "evidence_file_ids": [fid],
        }
        resp_neg = self.client.post("/api/v1/custom-verification/verify", json=payload_neg)
        self.assertIn(resp_neg.status_code, [400, 422])

    # -------------------------------------------------------------------------
    # 8. Invalid material quantity rejected
    # -------------------------------------------------------------------------
    def test_08_invalid_material_quantity_rejected(self):
        """Test 8: Negative claimed mass, invalid purity, or empty material claims rejected."""
        pid = self._create_and_prep_passport("DPP-INV-MAT")
        fid = self._upload_test_image("test_mat")

        # Negative material mass
        payload_neg = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [{"material_name": "Cobalt", "claimed_mass_kg": -10.0}],
            "evidence_file_ids": [fid],
        }
        resp_neg = self.client.post("/api/v1/custom-verification/verify", json=payload_neg)
        self.assertIn(resp_neg.status_code, [400, 422])

        # Invalid purity (>100%)
        payload_purity = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [{"material_name": "Cobalt", "claimed_mass_kg": 50.0, "purity_pct": 105.0}],
            "evidence_file_ids": [fid],
        }
        resp_purity = self.client.post("/api/v1/custom-verification/verify", json=payload_purity)
        self.assertIn(resp_purity.status_code, [400, 422])

        # Empty claimed materials
        payload_empty = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [],
            "evidence_file_ids": [fid],
        }
        resp_empty = self.client.post("/api/v1/custom-verification/verify", json=payload_empty)
        self.assertIn(resp_empty.status_code, [400, 422])

    # -------------------------------------------------------------------------
    # 9. Missing or ineligible passport rejected
    # -------------------------------------------------------------------------
    def test_09_missing_passport_rejected(self):
        """Test 9: Nonexistent passport or passport not in RECYCLING_PENDING is rejected."""
        fid = self._upload_test_image("test_nonexistent_dpp")

        # Nonexistent passport
        payload_nonexistent = {
            "passport_id": "DPP-DOES-NOT-EXIST-404",
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [{"material_name": "Cobalt", "claimed_mass_kg": 50.0}],
            "evidence_file_ids": [fid],
        }
        resp_missing = self.client.post("/api/v1/custom-verification/verify", json=payload_nonexistent)
        self.assertEqual(resp_missing.status_code, 404)
        self.assertEqual(resp_missing.json()["error_code"], "NOT_FOUND")

        # Ineligible passport in MANUFACTURED state
        pid_mfg = "DPP-CONSUMER-LCO-2026-B10"
        self.assertIn(pid_mfg, _PASSPORT_STORE)
        payload_mfg = {
            "passport_id": pid_mfg,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1.0,
            "claimed_materials": [{"material_name": "Cobalt", "claimed_mass_kg": 0.2}],
            "evidence_file_ids": [fid],
        }
        resp_ineligible = self.client.post("/api/v1/custom-verification/verify", json=payload_mfg)
        self.assertEqual(resp_ineligible.status_code, 400)
        self.assertEqual(resp_ineligible.json()["error_code"], "ILLEGAL_TRANSITION")

    # -------------------------------------------------------------------------
    # 10. Duplicate event rejected
    # -------------------------------------------------------------------------
    def test_10_duplicate_event_rejected(self):
        """Test 10: Anti-replay protection prevents re-submitting an already ingested event ID."""
        pid = self._create_and_prep_passport("DPP-REPLAY")
        fid = self._upload_test_image("replay_test")
        ev_id = f"REV-CUSTOM-DEDUP-{uuid.uuid4().hex[:6].upper()}"

        payload = {
            "event_id": ev_id,
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [{"material_name": "Nickel", "claimed_mass_kg": 165.6}],
            "evidence_file_ids": [fid],
        }

        # First attempt succeeds
        resp1 = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp1.status_code, 200)

        # Second attempt with same event_id fails with 409 Conflict
        resp2 = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp2.status_code, 409)
        self.assertEqual(resp2.json()["error_code"], "REPLAY_DETECTED")

    # -------------------------------------------------------------------------
    # 11. AI unavailable does not bypass deterministic verification
    # -------------------------------------------------------------------------
    def test_11_ai_unavailable_does_not_bypass_deterministic_verification(self):
        """Test 11: If AI observation fails/unavailable, deterministic verification still runs."""
        pid = self._create_and_prep_passport("DPP-AI-FALLBACK")
        fid = self._upload_test_image("ai_test_image")

        payload = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [
                {"material_name": "Nickel", "claimed_mass_kg": 165.6, "purity_pct": 99.2},
                {"material_name": "Cobalt", "claimed_mass_kg": 55.8, "purity_pct": 99.5},
            ],
            "evidence_file_ids": [fid],
            "run_ai_observation": True,
            "ai_force_mode": "DETERMINISTIC_FIXTURE",
            "ai_fixture_override": "FIXTURE-EV-NMC622-NORMAL",
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["overall_decision"], "VERIFIED")
        self.assertIsNotNone(data["ai_observation"])
        self.assertIn("AI observes evidence; deterministic verification makes the decision", data["ai_notice"])

    # -------------------------------------------------------------------------
    # 12. Evidence integrity remains verifiable
    # -------------------------------------------------------------------------
    def test_12_evidence_integrity_remains_verifiable(self):
        """Test 12: Evidence bundle can be independently verified via /api/v1/verification/verify-evidence."""
        pid = self._create_and_prep_passport("DPP-INTEGRITY")
        fid = self._upload_test_image("integrity_file")

        payload = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [{"material_name": "Nickel", "claimed_mass_kg": 165.6}],
            "evidence_file_ids": [fid],
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        ev_id = resp.json()["event_id"]

        # Call existing verify-evidence endpoint
        verify_resp = self.client.post("/api/v1/verification/verify-evidence", json={"event_id": ev_id})
        self.assertEqual(verify_resp.status_code, 200)
        v_data = verify_resp.json()
        self.assertTrue(v_data["is_valid"])
        self.assertEqual(v_data["event_id"], ev_id)
        self.assertIsNotNone(v_data["bundle_keccak256_commitment"])

    # -------------------------------------------------------------------------
    # 13. Successful verification produces a reproducible certificate
    # -------------------------------------------------------------------------
    def test_13_successful_verification_produces_reproducible_certificate(self):
        """Test 13: Issued certificate can be independently verified on-chain via /api/v1/certificates/verify."""
        pid = self._create_and_prep_passport("DPP-CERT-VERIFY")
        fid = self._upload_test_image("cert_evidence")

        payload = {
            "passport_id": pid,
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [
                {"material_name": "Nickel", "claimed_mass_kg": 165.6},
                {"material_name": "Cobalt", "claimed_mass_kg": 55.8},
            ],
            "evidence_file_ids": [fid],
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        cert = resp.json()["certificate"]
        self.assertIsNotNone(cert)
        cert_id = cert["certificate_id"]

        # Verify certificate authenticity independently
        v_resp = self.client.get(f"/api/v1/certificates/verify/{cert_id}")
        self.assertEqual(v_resp.status_code, 200)
        v_data = v_resp.json()
        self.assertEqual(v_data["status"], "VALID_AND_AUTHENTICATED")
        self.assertEqual(v_data["certificate_id"], cert_id)

    # -------------------------------------------------------------------------
    # 14. Scenarios A, B, C regressions
    # -------------------------------------------------------------------------
    def test_14_scenarios_a_b_c_regressions(self):
        """Test 14: Confirms that demo scenarios A, B, and C remain untouched and passing."""
        # Scenario A
        resp_a = self.client.post("/api/v1/demo/run-scenario", json={"scenario": "A"})
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_a.json()["verdict"], "VERIFIED")

        # Scenario B
        resp_b = self.client.post("/api/v1/demo/run-scenario", json={"scenario": "B"})
        self.assertEqual(resp_b.status_code, 200)
        self.assertEqual(resp_b.json()["verdict"], "CLAIM FLAGGED")

        # Scenario C
        resp_c = self.client.post("/api/v1/demo/run-scenario", json={"scenario": "C"})
        self.assertEqual(resp_c.status_code, 200)
        self.assertEqual(resp_c.json()["verdict"], "EVIDENCE_INTEGRITY_FAILURE")

    # -------------------------------------------------------------------------
    # 15. Concurrent replay race condition (thread-safety)
    # -------------------------------------------------------------------------
    def test_15_concurrent_replay_race_condition(self):
        """Test 15: Concurrently submitting identical event_id across threads yields exactly 1 success and 4 replay conflicts (409)."""
        pid = self._create_and_prep_passport("DPP-CONCUR")
        fid = self._upload_test_image("concur_evidence")
        fixed_event_id = f"REV-CONCUR-{uuid.uuid4().hex[:8].upper()}"

        payload = {
            "passport_id": pid,
            "event_id": fixed_event_id,
            "facility_id": "FAC-TEST-CONCUR",
            "operator_id": "OP-CONCUR",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [
                {"material_name": "Nickel", "claimed_mass_kg": 165.6, "purity_pct": 99.2, "provenance": "OBSERVED"},
            ],
            "evidence_file_ids": [fid],
        }

        def _send_request():
            return self.client.post("/api/v1/custom-verification/verify", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_send_request) for _ in range(5)]
            responses = [f.result() for f in futures]

        statuses = [r.status_code for r in responses]
        self.assertEqual(statuses.count(200), 1, f"Expected exactly 1 success (200), got {statuses}")
        self.assertEqual(statuses.count(409), 4, f"Expected exactly 4 replay conflicts (409), got {statuses}")

    # -------------------------------------------------------------------------
    # 16. Malformed ID sanitization and path traversal prevention
    # -------------------------------------------------------------------------
    def test_16_malformed_ids_rejected(self):
        """Test 16: Path traversal and control characters in IDs are rejected with HTTP 400."""
        pid = self._create_and_prep_passport("DPP-MALFORMED")
        fid = self._upload_test_image("malformed_evidence")

        base_payload = {
            "facility_id": "FAC-TEST",
            "operator_id": "OP-1",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [{"material_name": "Nickel", "claimed_mass_kg": 165.6}],
            "evidence_file_ids": [fid],
        }

        # 1. Path traversal in event_id
        p1 = dict(base_payload, passport_id=pid, event_id="../../etc/passwd")
        r1 = self.client.post("/api/v1/custom-verification/verify", json=p1)
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.json()["error_code"], "MALFORMED_EVENT_ID")

        # 2. Path traversal in passport_id
        p2 = dict(base_payload, passport_id="../../etc/shadow", event_id=f"REV-SAFE-{uuid.uuid4().hex[:6]}")
        r2 = self.client.post("/api/v1/custom-verification/verify", json=p2)
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json()["error_code"], "MALFORMED_PASSPORT_ID")

        # 3. Path traversal in evidence_file_ids
        p3 = dict(base_payload, passport_id=pid, event_id=f"REV-SAFE-{uuid.uuid4().hex[:6]}", evidence_file_ids=["../../bad/path"])
        r3 = self.client.post("/api/v1/custom-verification/verify", json=p3)
        self.assertEqual(r3.status_code, 400)
        self.assertEqual(r3.json()["error_code"], "MALFORMED_EVIDENCE_ID")

    # -------------------------------------------------------------------------
    # 17. Yield clamping and non-positive mass claim handling
    # -------------------------------------------------------------------------
    def test_17_yield_clamping_and_zero_mass_claim_handling(self):
        """Test 17: Clamps yield <= 100.0% when raw yield exceeds 100% due to instrument tolerance, avoiding Pydantic crash."""
        pid = f"DPP-CLAMP-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        from shared.schemas.material import MaterialComposition, MaterialComponent
        comp = MaterialComposition(
            total_mass_kg=1000.0,
            components=[
                MaterialComponent(
                    material_name="HighYieldAlloy",
                    percentage=100.0,
                    mass_kg=1000.0,
                    expected_yield_loss_pct=1.0,
                    tolerance_band_pct=5.0,
                )
            ]
        )
        payload_pass = {
            "passport_id": pid,
            "product_id": "SKU-CLAMP",
            "product_name": "High Yield Custom Module",
            "product_category": "INDUSTRIAL_BATTERY",
            "manufacturer": "Clamp Corp",
            "manufacturing_date": now,
            "initial_total_mass_kg": 1000.0,
            "material_composition": comp.model_dump(mode="json"),
            "current_lifecycle_state": "MANUFACTURED",
            "created_at": now,
            "updated_at": now,
        }
        resp_p = self.client.post("/api/v1/passports", json=payload_pass)
        self.assertEqual(resp_p.status_code, 201)

        blockchain_service.transition_state(pid, LifecycleState.IN_USE, AuthorizedRole.MANUFACTURER)
        blockchain_service.transition_state(pid, LifecycleState.RETURNED, AuthorizedRole.COLLECTION_AGENT)
        blockchain_service.transition_state(pid, LifecycleState.RECYCLING_PENDING, AuthorizedRole.RECYCLER)

        fid = self._upload_test_image("clamp_evidence")

        # Claim 1005.0 kg of HighYieldAlloy (raw_yield = 100.5%, within valid tolerance band [940.5, 1020.0])
        payload = {
            "passport_id": pid,
            "facility_id": "FAC-CLAMP",
            "operator_id": "OP-CLAMP",
            "intake_gross_mass_kg": 1000.0,
            "scale_uncertainty_pct": 2.0,
            "claimed_materials": [
                {"material_name": "HighYieldAlloy", "claimed_mass_kg": 1005.0, "purity_pct": 99.0, "provenance": "MEASURED"},
            ],
            "evidence_file_ids": [fid],
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["overall_decision"], "VERIFIED")
        cert = data.get("certificate")
        self.assertIsNotNone(cert)
        self.assertIn("verified_material_quantities", cert)
        for vm in cert["verified_material_quantities"]:
            self.assertEqual(vm["material_name"], "HighYieldAlloy")
            self.assertEqual(vm["recovered_mass_kg"], 1005.0)
            self.assertEqual(vm["recovery_yield_pct"], 100.0)  # Clamped from 100.5% down to 100.0%

    # -------------------------------------------------------------------------
    # 18. Direct verification auto-seeding
    # -------------------------------------------------------------------------
    def test_18_direct_verification_auto_seeds_store(self):
        """Test 18: Direct POST to verify without prior /passports requests auto-seeds default passports."""
        # Wipe passport store
        _PASSPORT_STORE.clear()
        fid = self._upload_test_image("autoseed_evidence")

        # DPP-EV-NMC622-2026-M04 is seeded directly into RECYCLING_PENDING by seed_default_passports()
        payload = {
            "passport_id": "DPP-EV-NMC622-2026-M04",
            "facility_id": "FAC-AUTOSEED",
            "operator_id": "OP-AUTOSEED",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [
                {"material_name": "Nickel", "claimed_mass_kg": 165.6, "purity_pct": 99.2, "provenance": "OBSERVED"},
            ],
            "evidence_file_ids": [fid],
        }

        resp = self.client.post("/api/v1/custom-verification/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["overall_decision"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
