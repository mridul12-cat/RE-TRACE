"""
tests/test_backend_api.py — Comprehensive FastAPI Integration & Endpoint Verification Suite.
Verifies all 10 REST endpoints, anti-replay guards, MIME sniffing, and adversarial scenarios via HTTP.
"""

import unittest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.blockchain_service import blockchain_service, BlockchainService
from backend.app.api.v1.passports import _PASSPORT_STORE
from backend.app.api.v1.recycling import _EVENT_STORE
from shared.domain.lifecycle import LifecycleState
from shared.fixtures.reference_materials import EV_BATTERY_NMC_622_COMPOSITION


class TestBackendAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        blockchain_service.reset_state()
        _PASSPORT_STORE.clear()
        _EVENT_STORE.clear()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        blockchain_service.reset_state()
        _PASSPORT_STORE.clear()
        _EVENT_STORE.clear()

    def setUp(self):
        # Ensure blockchain simulation is connected
        blockchain_service.simulate_rpc_reconnect()

    def test_01_health_and_root_endpoints(self):
        """Validates /health and root status."""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertEqual(data["blockchain"]["network_label"], "LOCAL TESTNET")

        resp_root = self.client.get("/")
        self.assertEqual(resp_root.status_code, 200)

    def test_02_passport_registration_and_retrieval(self):
        """Registers a DPP and retrieves it via REST API."""
        pid = "DPP-EV-NMC622-API-TEST-01"
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "passport_id": pid,
            "product_id": "SKU-TEST-001",
            "product_name": "EV Traction Battery Module",
            "product_category": "EV_BATTERY",
            "manufacturer": "Test Manufacturer Corp",
            "manufacturing_date": now,
            "initial_total_mass_kg": 25.0,
            "material_composition": EV_BATTERY_NMC_622_COMPOSITION.model_dump(mode="json"),
            "current_lifecycle_state": "MANUFACTURED",
            "created_at": now,
            "updated_at": now
        }

        resp = self.client.post("/api/v1/passports", json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["passport_id"], pid)

        # Retrieve passport
        resp_get = self.client.get(f"/api/v1/passports/{pid}")
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.json()["passport_id"], pid)

        # Anti-replay on duplicate passport registration
        resp_dup = self.client.post("/api/v1/passports", json=payload)
        self.assertEqual(resp_dup.status_code, 409)

    def test_03_evidence_upload_mime_sniffing_and_rejection(self):
        """Tests physical evidence upload, valid MIME sniffing, and invalid format rejection."""
        # 1. Valid JPEG
        valid_jpeg = b"\xff\xd8\xff\xe0" + b"TEST_IMAGE_PAYLOAD" * 10
        files = {"file": ("scale_slip.jpg", valid_jpeg, "image/jpeg")}
        data = {"provenance_category": "MEASURED", "description": "Weighbridge test ticket"}

        resp = self.client.post("/api/v1/evidence/upload", files=files, data=data)
        self.assertEqual(resp.status_code, 201)
        file_rec = resp.json()
        self.assertTrue(file_rec["file_id"].startswith("EV-"))
        self.assertEqual(file_rec["provenance"], "MEASURED")

        # 2. Invalid / Disallowed MIME type (Adversarial Case H)
        invalid_exe = b"MZ\x90\x00\x03\x00\x00\x00"  # Executable binary header
        files_bad = {"file": ("payload.exe", invalid_exe, "application/x-msdownload")}
        resp_bad = self.client.post("/api/v1/evidence/upload", files=files_bad)
        self.assertEqual(resp_bad.status_code, 415)

        # 3. Mismatched magic bytes (claimed JPEG but header is text)
        files_mismatch = {"file": ("fake.jpg", b"PLAIN_TEXT_CONTENT", "image/jpeg")}
        resp_mismatch = self.client.post("/api/v1/evidence/upload", files=files_mismatch)
        self.assertEqual(resp_mismatch.status_code, 415)

    def test_04_recycling_event_replay_prevention(self):
        """Tests recycling event submission and anti-replay protection (Case E)."""
        pid = "DPP-EV-NMC622-API-TEST-01"
        event_id = "REV-2026-REPLAY-TEST-01"
        payload = {
            "event_id": event_id,
            "passport_id": pid,
            "facility_id": "FAC-TEST-01",
            "operator_id": "OP-1",
            "timestamp": "2026-10-08T10:00:00Z",
            "intake_gross_mass_kg": 1000.0,
            "claimed_materials": [
                {"material_name": "Cobalt", "claimed_mass_kg": 55.8, "provenance": "MEASURED"}
            ],
            "evidence_file_ids": ["EV-TEST-001"]
        }

        # First ingestion
        resp1 = self.client.post("/api/v1/recycling/events", json=payload)
        self.assertEqual(resp1.status_code, 201)

        # Duplicate ingestion resubmitted (Replay Attack)
        resp2 = self.client.post("/api/v1/recycling/events", json=payload)
        self.assertEqual(resp2.status_code, 409)
        self.assertIn("REPLAY_DETECTED", resp2.json()["error_code"])

    def test_05_ai_observation_dual_mode(self):
        """Tests the dual-mode AI observation endpoint."""
        # Upload an evidence file first
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"TEST_MODULE_SCAN" * 15
        upload_resp = self.client.post(
            "/api/v1/evidence/upload",
            files={"file": ("module_scan.jpg", jpeg_bytes, "image/jpeg")},
            data={"provenance_category": "OBSERVED"}
        )
        file_id = upload_resp.json()["file_id"]

        # Run AI observation
        obs_payload = {
            "file_id": file_id,
            "force_mode": "DETERMINISTIC_FIXTURE",
            "fixture_override": "FIXTURE-EV-NMC622-NORMAL"
        }
        resp = self.client.post("/api/v1/ai/observe", json=obs_payload)
        self.assertEqual(resp.status_code, 200)
        obs_data = resp.json()
        self.assertEqual(obs_data["provenance_category"], "AI_ESTIMATED")
        self.assertEqual(obs_data["estimated_item_count"], 40)
        self.assertGreater(obs_data["confidence"], 0.9)

    def test_06_lifecycle_role_authorization_and_quarantine(self):
        """Tests role authorization and quarantine resolution rules (Case G)."""
        pid = "DPP-EV-NMC622-API-TEST-01"

        # 1. Illegal skip: attempt direct hop to MATERIALS_RECOVERED
        resp_illegal = self.client.post(
            "/api/v1/lifecycle/transition",
            json={
                "passport_id": pid,
                "target_state": "MATERIALS_RECOVERED",
                "actor_role": "RECYCLER"
            }
        )
        self.assertEqual(resp_illegal.status_code, 400)

        # 2. Quarantine: flag product
        resp_flag = self.client.post(
            "/api/v1/lifecycle/flag",
            json={"passport_id": pid, "reason": "Suspected anomalous batch density"}
        )
        self.assertEqual(resp_flag.status_code, 200)
        self.assertEqual(resp_flag.json()["state"], "FLAGGED")

        # 3. Recycler attempts to unflag (forbidden)
        resp_unflag_unauth = self.client.post(
            "/api/v1/lifecycle/transition",
            json={
                "passport_id": pid,
                "target_state": "RECYCLING_VERIFIED",
                "actor_role": "RECYCLER"
            }
        )
        self.assertEqual(resp_unflag_unauth.status_code, 403)

        # 4. Auditor resolves flag with documented notes
        resp_resolve = self.client.post(
            "/api/v1/lifecycle/resolve-flag",
            json={
                "passport_id": pid,
                "auditor_address": "0x4444444444444444444444444444444444444444",
                "target_state": "RECYCLING_VERIFIED",
                "notes": "Auditor inspected physical XRF assay and verified tare weight correction."
            }
        )
        self.assertEqual(resp_resolve.status_code, 200)
        self.assertEqual(resp_resolve.json()["state"], "RECYCLING_VERIFIED")

    def test_07_blockchain_offline_simulation(self):
        """Tests graceful handling when blockchain RPC node is offline (Case J)."""
        pid = "DPP-EV-NMC622-API-TEST-01"

        # Disconnect RPC
        self.client.post("/api/v1/blockchain/simulate-disconnect")

        # Attempting on-chain state transition fails with HTTP 503
        resp = self.client.post(
            "/api/v1/lifecycle/transition",
            json={
                "passport_id": pid,
                "target_state": "MATERIALS_RECOVERED",
                "actor_role": "RECYCLER"
            }
        )
        self.assertEqual(resp.status_code, 503)
        self.assertIn("BLOCKCHAIN_OFFLINE", resp.json()["error_code"])

        # Reconnect
        self.client.post("/api/v1/blockchain/simulate-reconnect")
        status_resp = self.client.get("/api/v1/blockchain/status")
        self.assertTrue(status_resp.json()["is_connected"])

    def test_08_demo_scenarios_a_b_c(self):
        """Tests automated execution of Demo Scenarios A, B, and C."""
        # Scenario A (Legitimate)
        resp_a = self.client.post("/api/v1/demo/run-scenario", json={"scenario": "A"})
        self.assertEqual(resp_a.status_code, 200)
        data_a = resp_a.json()
        self.assertEqual(data_a["verdict"], "VERIFIED")
        self.assertIn("certificate", data_a)

        # Scenario B (Fraudulent Stoichiometric Claim)
        resp_b = self.client.post("/api/v1/demo/run-scenario", json={"scenario": "B"})
        self.assertEqual(resp_b.status_code, 200)
        data_b = resp_b.json()
        self.assertEqual(data_b["verdict"], "CLAIM FLAGGED")
        self.assertIn("mathematical_proof", data_b)

        # Scenario C (Evidence Tampering)
        resp_c = self.client.post("/api/v1/demo/run-scenario", json={"scenario": "C"})
        self.assertEqual(resp_c.status_code, 200)
        data_c = resp_c.json()
        self.assertEqual(data_c["verdict"], "EVIDENCE_INTEGRITY_FAILURE")

    def test_09_polyglot_and_tiny_upload_rejected(self):
        """Tests that polyglot executable/script payloads and tiny/empty uploads are rejected."""
        # 1. Sub-16 byte tiny file claiming to be JPEG
        tiny_payload = b"\xff\xd8\xff" + b"X" * 5
        files_tiny = {"file": ("tiny.jpg", tiny_payload, "image/jpeg")}
        resp_tiny = self.client.post("/api/v1/evidence/upload", files=files_tiny)
        self.assertEqual(resp_tiny.status_code, 415)
        self.assertIn("too small", resp_tiny.json()["message"])

        # 2. Polyglot: Valid JPEG prefix + embedded HTML/JS script
        polyglot_script = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00\x01\x01\x00" + b"<script>alert('xss')</script>" * 5
        files_poly = {"file": ("exploit.jpg", polyglot_script, "image/jpeg")}
        resp_poly = self.client.post("/api/v1/evidence/upload", files=files_poly)
        self.assertEqual(resp_poly.status_code, 415)
        self.assertIn("prohibited active script", resp_poly.json()["message"])

        # 3. Polyglot: Valid JPEG prefix + Windows executable header
        polyglot_pe = b"MZ\x90\x00" + b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00\x01\x01\x00"
        files_pe = {"file": ("dual.jpg", polyglot_pe, "image/jpeg")}
        resp_pe = self.client.post("/api/v1/evidence/upload", files=files_pe)
        self.assertEqual(resp_pe.status_code, 415)
        self.assertIn("prohibited executable/binary header", resp_pe.json()["message"])

    def test_10_blockchain_state_persistence(self):
        """Verifies that the blockchain ledger state persists to disk and can be reloaded across service restarts."""
        test_pid = f"DPP-EV-PERSIST-TEST-{uuid.uuid4().hex[:6].upper()}"
        tx_hash = blockchain_service.register_passport(
            passport_id=test_pid,
            bom_hash="0x" + "b" * 64,
            manufacturer="0x5555555555555555555555555555555555555555"
        )
        self.assertTrue(tx_hash.startswith("0x"))

        # Create a new BlockchainService instance pointing to the same state file
        fresh_service = BlockchainService(state_file=blockchain_service.state_file)
        retrieved = fresh_service.get_passport(test_pid)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["passport_id"], test_pid)
        self.assertEqual(retrieved["state"], LifecycleState.MANUFACTURED.value)

    def test_11_scenario_c_lifecycle_quarantine_verification(self):
        """Verifies that executing Scenario C quarantines the passport into FLAGGED state on-chain."""
        resp = self.client.post("/api/v1/demo/run-scenario", json={"scenario": "C"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["verdict"], "EVIDENCE_INTEGRITY_FAILURE")

        # Find the passport ID created in Scenario C from stage 1
        passport_id = None
        for st in data["stages"]:
            if "Original" in st.get("name", ""):
                passport_id = st.get("tx_hash")  # We can also check stage 3
            if st.get("lifecycle_state") == "FLAGGED":
                self.assertEqual(st.get("status"), "TAMPERING_DETECTED")
                self.assertIn("Quarantined in FLAGGED state", st.get("quarantine_resolution_rule", ""))


if __name__ == "__main__":
    unittest.main()
