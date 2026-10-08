"""
tests/test_gemini_vision_integration.py — Comprehensive Automated Test Suite
for Real Gemini Vision Multimodal Integration & Trustworthiness.

Covers all 12 validation requirements from RE:TRACE Critical AI Evidence-Truthfulness Task:
1. Fixture mode isolation (offline replay, SIMULATED provenance, zero API traffic)
2. Live Gemini success using mocked multimodal Gemini response (1 unit observed, NOT 15 or 40)
3. Provider and model metadata integrity
4. AI_ESTIMATED provenance on live responses
5. Missing API key handling (GeminiNotConfiguredError, explicit fallback labeling)
6. Gemini API failure modes (401 auth, 429 quota, 503 unavailable, network timeout)
7. Malformed Gemini response handling (markdown code blocks, invalid JSON)
8. Invalid evidence input validation (empty bytes, corrupt files)
9. No silent fixture fallback (visible labeling, SIMULATED provenance, failure reason)
10. Frontend/backend execution-mode consistency
11. Evidence ID and cryptographic SHA-256 propagation
12. Preservation of deterministic mass-balance verification trust boundary
"""

import os
import sys
import glob
import json
import uuid
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

# Path bootstrapping: Ensure project root and .venv site-packages are in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

venv_patterns = [
    os.path.join(PROJECT_ROOT, ".venv", "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages"),
    os.path.join(PROJECT_ROOT, ".venv", "lib", "python*", "site-packages"),
]
for pat in venv_patterns:
    for matched_path in glob.glob(pat):
        if os.path.isdir(matched_path) and matched_path not in sys.path:
            sys.path.insert(0, matched_path)

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.errors import (
    GeminiNotConfiguredError,
    GeminiAuthError,
    GeminiRateLimitError,
    GeminiUnavailableError,
    GeminiInvalidResponseError,
    GeminiImageRejectedError,
)
from backend.app.services.storage_service import storage_service
from ml.inference.dual_mode_observer import DualModeAIObservationService
from ml.models.vision_schemas import AIObservationResult, DetectedItem
from shared.schemas.provenance import ProvenanceCategory
from datetime import datetime, timezone
from shared.domain.lifecycle import LifecycleState, AuthorizedRole
from shared.fixtures.reference_materials import EV_BATTERY_NMC_622_COMPOSITION
from backend.app.services.blockchain_service import blockchain_service


class TestGeminiVisionIntegration(unittest.TestCase):
    """
    Automated test suite verifying the Gemini Vision integration without requiring live network/API calls in CI.
    """

    def setUp(self):
        self.client = TestClient(app)
        self.ai_service = DualModeAIObservationService(default_mode="AUTO", api_key="test-mock-key")
        # Minimal valid JPEG image bytes (SOI + APP0 marker + data)
        self.valid_jpeg_bytes = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            + b"MOCK_SINGLE_BATTERY_PICTURE_DATA_" + uuid.uuid4().hex.encode("utf-8")
        )

    def _upload_test_image(self, tag: str = "img") -> str:
        content = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            + f"RETRACE_EVIDENCE_{tag}_{uuid.uuid4().hex}".encode("utf-8") * 4
        )
        resp = self.client.post(
            "/api/v1/evidence/upload",
            files={"file": (f"test_{tag}.jpg", content, "image/jpeg")},
            data={"provenance_category": "MEASURED", "description": f"Test image {tag}"}
        )
        self.assertEqual(resp.status_code, 201)
        return resp.json()["file_id"]

    def _create_and_prep_passport(self, base_id: str) -> str:
        pid = f"{base_id}-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "passport_id": pid,
            "product_id": "SKU-TEST-BATTERY",
            "product_name": "EV Traction Battery Pack NMC 622",
            "product_category": "EV_BATTERY",
            "manufacturer": "Circulor Battery Corp",
            "manufacturing_date": now,
            "initial_total_mass_kg": 1000.0,
            "material_composition": EV_BATTERY_NMC_622_COMPOSITION.model_dump(mode="json"),
            "current_lifecycle_state": "MANUFACTURED",
            "created_at": now,
            "updated_at": now,
        }
        resp = self.client.post("/api/v1/passports", json=payload)
        self.assertEqual(resp.status_code, 201)

        blockchain_service.transition_state(pid, LifecycleState.IN_USE, AuthorizedRole.MANUFACTURER)
        blockchain_service.transition_state(pid, LifecycleState.RETURNED, AuthorizedRole.COLLECTION_AGENT)
        blockchain_service.transition_state(pid, LifecycleState.RECYCLING_PENDING, AuthorizedRole.RECYCLER)
        return pid

    # -------------------------------------------------------------------------
    # 1. Fixture Mode Isolation
    # -------------------------------------------------------------------------
    def test_01_fixture_mode_isolation(self):
        """
        Req 1 & 10: In DETERMINISTIC_FIXTURE mode, evidence is NOT sent to Gemini.
        Returns execution_mode=DETERMINISTIC_FIXTURE, provider=deterministic-replay, provenance=SIMULATED.
        """
        with patch.object(self.ai_service, "_call_gemini_api") as mock_gemini:
            res = self.ai_service.observe(
                file_bytes=self.valid_jpeg_bytes,
                filename="battery_photo.jpg",
                mime_type="image/jpeg",
                force_mode="DETERMINISTIC_FIXTURE",
                evidence_id="EV-TEST-001",
                evidence_sha256="abc123hash",
            )
            mock_gemini.assert_not_called()
            self.assertEqual(res.execution_mode, "DETERMINISTIC_FIXTURE")
            self.assertEqual(res.provider, "deterministic-replay")
            self.assertEqual(res.provenance, "SIMULATED")
            self.assertEqual(res.evidence_id, "EV-TEST-001")
            self.assertEqual(res.evidence_sha256, "abc123hash")

    # -------------------------------------------------------------------------
    # 2. Live Gemini Success Using Mocked Multimodal Gemini Response
    # -------------------------------------------------------------------------
    def test_02_live_gemini_success_mocked_one_battery(self):
        """
        Req 2: When user submits a 1-battery image under LIVE_GEMINI,
        the model observation reflects the actual response (1 Unit, NOT 15 or 40 Units).
        """
        mock_gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "detected_items": [
                                        {"label": "EV_BATTERY_MODULE_SINGLE", "count": 1, "confidence": 0.98}
                                    ],
                                    "estimated_item_count": 1,
                                    "estimated_gross_mass_kg": 24.8,
                                    "confidence": 0.98,
                                    "material_estimates": {
                                        "Nickel": 4.14,
                                        "Cobalt": 1.40,
                                        "Lithium": 0.53
                                    },
                                    "anomaly_flags": [],
                                    "notes": "Single EV battery module inspected cleanly on scale pallet."
                                })
                            }
                        ]
                    }
                }
            ]
        }

        with patch.object(self.ai_service, "_call_gemini_api", return_value=mock_gemini_response) as mock_api:
            res = self.ai_service.observe(
                file_bytes=self.valid_jpeg_bytes,
                filename="single_battery.jpg",
                mime_type="image/jpeg",
                force_mode="LIVE_GEMINI",
                evidence_id="EV-ONE-BATTERY",
                evidence_sha256="deadbeef1234",
            )
            mock_api.assert_called_once()
            # Assert payload sent to Gemini has inline_data
            payload = mock_api.call_args[0][0]
            inline_part = payload["contents"][0]["parts"][1]["inline_data"]
            self.assertEqual(inline_part["mime_type"], "image/jpeg")
            self.assertTrue(len(inline_part["data"]) > 0)

            # Assert observed output is 1 unit (NOT fixture 15 or 40!)
            self.assertEqual(res.execution_mode, "LIVE_GEMINI")
            self.assertEqual(res.provider, "google-gemini")
            self.assertEqual(res.model, "gemini-2.5-flash")
            self.assertEqual(res.estimated_item_count, 1)
            self.assertNotEqual(res.estimated_item_count, 15)
            self.assertNotEqual(res.estimated_item_count, 40)
            self.assertEqual(res.provenance, "AI_ESTIMATED")
            self.assertEqual(res.evidence_id, "EV-ONE-BATTERY")
            self.assertEqual(res.evidence_sha256, "deadbeef1234")
            self.assertIn("Single EV battery module", res.notes)

    # -------------------------------------------------------------------------
    # 3. Provider and Model Metadata
    # -------------------------------------------------------------------------
    def test_03_provider_and_model_metadata(self):
        """
        Req 3: Provider must be 'google-gemini' and model must match configured model.
        """
        mock_resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps({"estimated_item_count": 2, "confidence": 0.91, "notes": "Two units."})}
                        ]
                    }
                }
            ]
        }
        custom_service = DualModeAIObservationService(
            default_mode="LIVE_GEMINI",
            api_key="mock-key",
            model="gemini-2.0-flash"
        )
        with patch.object(custom_service, "_call_gemini_api", return_value=mock_resp):
            res = custom_service.observe(self.valid_jpeg_bytes, force_mode="LIVE_GEMINI")
            self.assertEqual(res.provider, "google-gemini")
            self.assertEqual(res.model, "gemini-2.0-flash")

    # -------------------------------------------------------------------------
    # 4. AI_ESTIMATED Provenance
    # -------------------------------------------------------------------------
    def test_04_ai_estimated_provenance_on_live(self):
        """
        Req 4: Successful live Gemini execution strictly produces AI_ESTIMATED provenance.
        """
        mock_resp = {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps({"estimated_item_count": 3, "confidence": 0.88})}]}}
            ]
        }
        with patch.object(self.ai_service, "_call_gemini_api", return_value=mock_resp):
            res = self.ai_service.observe(self.valid_jpeg_bytes, force_mode="LIVE_GEMINI")
            self.assertEqual(res.provenance, "AI_ESTIMATED")
            self.assertEqual(res.provenance_category, ProvenanceCategory.AI_ESTIMATED)

    # -------------------------------------------------------------------------
    # 5. Missing API Key Handling
    # -------------------------------------------------------------------------
    def test_05_missing_api_key_handling(self):
        """
        Req 5: Missing GEMINI_API_KEY is rejected cleanly without crashing or silent masquerading.
        """
        service_no_key = DualModeAIObservationService(default_mode="AUTO", api_key=None)
        with patch.dict(os.environ, {}, clear=True):
            # Without fallback: raises GeminiNotConfiguredError
            with self.assertRaises(GeminiNotConfiguredError):
                service_no_key.observe(
                    self.valid_jpeg_bytes,
                    force_mode="LIVE_GEMINI",
                    allow_fallback=False
                )

            # With fallback enabled (e.g. custom verification workflow):
            res = service_no_key.observe(
                self.valid_jpeg_bytes,
                force_mode="LIVE_GEMINI",
                allow_fallback=True
            )
            self.assertEqual(res.execution_mode, "DETERMINISTIC_FIXTURE")
            self.assertEqual(res.provenance, "SIMULATED")
            self.assertIn("GEMINI_NOT_CONFIGURED", res.notes)

    # -------------------------------------------------------------------------
    # 6. Gemini API Failure Modes (401, 429, 503, Timeout)
    # -------------------------------------------------------------------------
    def test_06_gemini_api_failure_modes(self):
        """
        Req 6: Standardized domain exceptions for HTTP 401, 429, 503, and network timeouts.
        Credentials must never leak into exception messages.
        """
        secret_key = "secret_ai_key_xyz987"
        service = DualModeAIObservationService(default_mode="LIVE_GEMINI", api_key=secret_key)

        # 1. HTTP 401 Authentication Error
        http_err_401 = urllib.error.HTTPError(
            url="https://api.test", code=401, msg="Unauthorized", hdrs={}, fp=MagicMock(read=lambda: b"Invalid API key " + secret_key.encode())
        )
        with patch("urllib.request.urlopen", side_effect=http_err_401):
            with self.assertRaises(GeminiAuthError) as ctx:
                service._call_gemini_api({"contents": []})
            self.assertIn("GEMINI_AUTHENTICATION_FAILED", str(ctx.exception))
            self.assertNotIn(secret_key, str(ctx.exception))

        # 2. HTTP 429 Rate Limit Error
        http_err_429 = urllib.error.HTTPError(
            url="https://api.test", code=429, msg="Rate limit exceeded", hdrs={}, fp=MagicMock(read=lambda: b"Quota reached")
        )
        with patch("urllib.request.urlopen", side_effect=http_err_429):
            with self.assertRaises(GeminiRateLimitError):
                service._call_gemini_api({"contents": []})

        # 3. HTTP 503 Service Unavailable
        http_err_503 = urllib.error.HTTPError(
            url="https://api.test", code=503, msg="Service Unavailable", hdrs={}, fp=MagicMock(read=lambda: b"Busy")
        )
        with patch("urllib.request.urlopen", side_effect=http_err_503):
            with self.assertRaises(GeminiUnavailableError):
                service._call_gemini_api({"contents": []})

        # 4. Network Timeout
        with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
            with self.assertRaises(GeminiUnavailableError) as ctx:
                service._call_gemini_api({"contents": []})
            self.assertIn("timeout", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 7. Malformed Gemini Response Handling
    # -------------------------------------------------------------------------
    def test_07_malformed_gemini_response(self):
        """
        Req 7: Malformed JSON or empty candidates raise GeminiInvalidResponseError.
        Markdown code blocks (```json ... ```) are cleanly parsed.
        """
        # Case A: Markdown code fence around JSON is parsed successfully
        wrapped_json = "```json\n{\"estimated_item_count\": 5, \"confidence\": 0.92, \"notes\": \"Clean parse\"}\n```"
        mock_wrapped_resp = {"candidates": [{"content": {"parts": [{"text": wrapped_json}]}}]}
        with patch.object(self.ai_service, "_call_gemini_api", return_value=mock_wrapped_resp):
            res = self.ai_service.observe(self.valid_jpeg_bytes, force_mode="LIVE_GEMINI")
            self.assertEqual(res.estimated_item_count, 5)

        # Case B: Unparseable non-JSON text raises GeminiInvalidResponseError
        bad_resp = {"candidates": [{"content": {"parts": [{"text": "Sorry, I cannot analyze this image as an AI."}]}}]}
        with patch.object(self.ai_service, "_call_gemini_api", return_value=bad_resp):
            with self.assertRaises(GeminiInvalidResponseError):
                self.ai_service.observe(self.valid_jpeg_bytes, force_mode="LIVE_GEMINI", allow_fallback=False)

        # Case C: Empty candidates raises GeminiInvalidResponseError
        empty_resp = {"candidates": []}
        with patch.object(self.ai_service, "_call_gemini_api", return_value=empty_resp):
            with self.assertRaises(GeminiInvalidResponseError):
                self.ai_service.observe(self.valid_jpeg_bytes, force_mode="LIVE_GEMINI", allow_fallback=False)

    # -------------------------------------------------------------------------
    # 8. Invalid Evidence Rejection
    # -------------------------------------------------------------------------
    def test_08_invalid_evidence_rejection(self):
        """
        Req 8: Empty or corrupt image content is rejected with GeminiImageRejectedError.
        """
        # Empty bytes
        with self.assertRaises(GeminiImageRejectedError):
            self.ai_service.observe(b"", force_mode="LIVE_GEMINI", allow_fallback=False)

        # Tiny truncated bytes < 16 bytes
        with self.assertRaises(GeminiImageRejectedError):
            self.ai_service.observe(b"\xff\xd8\xff", force_mode="LIVE_GEMINI", allow_fallback=False)

        # Unsupported MIME format
        with self.assertRaises(GeminiImageRejectedError):
            self.ai_service.observe(
                self.valid_jpeg_bytes,
                mime_type="audio/mp3",
                force_mode="LIVE_GEMINI",
                allow_fallback=False
            )

    # -------------------------------------------------------------------------
    # 9. No Silent Fixture Fallback
    # -------------------------------------------------------------------------
    def test_09_no_silent_fixture_fallback_in_custom_verification(self):
        """
        Req 9: If user selects LIVE_GEMINI and Gemini fails,
        the system MUST NOT silently substitute fixture data without explicit fallback flagging.
        """
        fid = self._upload_test_image("no_silent")
        pid = self._create_and_prep_passport("DPP-NO-SILENT")

        req = {
            "passport_id": pid,
            "intake_gross_mass_kg": 25.0,
            "claimed_materials": [{"material_name": "Nickel", "claimed_mass_kg": 4.14, "purity_pct": 99.0}],
            "evidence_file_ids": [fid],
            "run_ai_observation": True,
            "ai_force_mode": "LIVE_GEMINI",
        }

        # Simulate Gemini unavailable during verification
        with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-key"}):
            with patch("ml.inference.dual_mode_observer.DualModeAIObservationService._call_gemini_api",
                       side_effect=GeminiUnavailableError("GEMINI_UNAVAILABLE: HTTP 503")):
                res = self.client.post("/api/v1/custom-verification/verify", json=req)
                self.assertEqual(res.status_code, 200)
                data = res.json()

                # Must be explicitly flagged as fallback
                self.assertTrue(data["ai_fallback_occurred"])
                self.assertEqual(data["ai_requested_mode"], "LIVE_GEMINI")
                self.assertIn("GEMINI_UNAVAILABLE", data["ai_fallback_reason"])

                obs = data["ai_observation"]
                self.assertEqual(obs["execution_mode"], "DETERMINISTIC_FIXTURE")
                self.assertEqual(obs["provider"], "deterministic-replay")
                self.assertEqual(obs["provenance"], "SIMULATED")

    # -------------------------------------------------------------------------
    # 10. Frontend / Backend Execution-Mode Consistency
    # -------------------------------------------------------------------------
    def test_10_frontend_backend_execution_mode_consistency(self):
        """
        Req 10: Backend responses drive truthful UI state.
        Never label deterministic fixture as LIVE_GEMINI.
        """
        fid = self._upload_test_image("fe_be_test")
        pid = self._create_and_prep_passport("DPP-FE-BE")

        mock_gemini_resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "detected_items": [{"label": "EV_BATTERY_MODULE_6S2P", "count": 2, "confidence": 0.95}],
                                    "estimated_item_count": 2,
                                    "confidence": 0.95,
                                    "notes": "Verified Gemini visual inference."
                                })
                            }
                        ]
                    }
                }
            ]
        }

        req = {
            "passport_id": pid,
            "intake_gross_mass_kg": 25.0,
            "claimed_materials": [{"material_name": "Nickel", "claimed_mass_kg": 4.14, "purity_pct": 99.0}],
            "evidence_file_ids": [fid],
            "run_ai_observation": True,
            "ai_force_mode": "LIVE_GEMINI",
        }

        with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-key"}):
            with patch("ml.inference.dual_mode_observer.DualModeAIObservationService._call_gemini_api",
                       return_value=mock_gemini_resp):
                res = self.client.post("/api/v1/custom-verification/verify", json=req)
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertFalse(data["ai_fallback_occurred"])
                self.assertEqual(data["ai_observation"]["execution_mode"], "LIVE_GEMINI")
                self.assertEqual(data["ai_observation"]["provider"], "google-gemini")
                self.assertEqual(data["ai_observation"]["provenance"], "AI_ESTIMATED")
                self.assertEqual(data["ai_observation"]["estimated_item_count"], 2)

    # -------------------------------------------------------------------------
    # 11. Evidence ID Propagation
    # -------------------------------------------------------------------------
    def test_11_evidence_id_propagation(self):
        """
        Req 11: The specific uploaded evidence artifact ID and SHA-256 propagate into the observation result.
        """
        fid = self._upload_test_image("ev_prop")
        record = storage_service.get_record(fid)
        self.assertIsNotNone(record)

        mock_gemini_resp = {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps({"estimated_item_count": 1, "confidence": 0.93})}]}}
            ]
        }

        with patch.object(self.ai_service, "_call_gemini_api", return_value=mock_gemini_resp):
            content = storage_service.get_content(fid)
            res = self.ai_service.observe(
                file_bytes=content,
                filename=record.filename,
                mime_type=record.mime_type,
                force_mode="LIVE_GEMINI",
                evidence_id=record.file_id,
                evidence_sha256=record.sha256_hash,
            )
            self.assertEqual(res.evidence_id, record.file_id)
            self.assertEqual(res.evidence_sha256, record.sha256_hash)

    # -------------------------------------------------------------------------
    # 12. Deterministic Verification Remains Authoritative
    # -------------------------------------------------------------------------
    def test_12_deterministic_verification_remains_authoritative(self):
        """
        Req 12: AI observations furnish feature priors and unit estimates only.
        The deterministic mass-balance engine and blockchain anchoring remain authoritative.
        """
        fid = self._upload_test_image("auth_boundary")
        pid = self._create_and_prep_passport("DPP-AUTH-GATE")

        # Legitimate claim matching BoM
        valid_req = {
            "passport_id": pid,
            "intake_gross_mass_kg": 25.0,
            "claimed_materials": [
                {"material_name": "Nickel", "claimed_mass_kg": 4.14, "purity_pct": 99.0},
                {"material_name": "Cobalt", "claimed_mass_kg": 1.40, "purity_pct": 99.0},
            ],
            "evidence_file_ids": [fid],
            "run_ai_observation": True,
            "ai_force_mode": "LIVE_GEMINI",
        }

        mock_gemini_resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "estimated_item_count": 1,
                                    "confidence": 0.95,
                                    "material_estimates": {"Nickel": 4.14, "Cobalt": 1.40}
                                })
                            }
                        ]
                    }
                }
            ]
        }

        with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-key"}):
            with patch("ml.inference.dual_mode_observer.DualModeAIObservationService._call_gemini_api",
                       return_value=mock_gemini_resp):
                res = self.client.post("/api/v1/custom-verification/verify", json=valid_req)
                self.assertEqual(res.status_code, 200)
                data = res.json()
                # Verification verdict is governed by mass balance
                self.assertEqual(data["overall_decision"], "VERIFIED")
                self.assertEqual(data["mass_balance_decision"], "VALID")
                self.assertTrue(data["blockchain"]["is_anchored"])
                self.assertIsNotNone(data["certificate"])

    # -------------------------------------------------------------------------
    # 13. Gemini Reasoning / Thought Parts Handling
    # -------------------------------------------------------------------------
    def test_13_gemini_thought_parts_reasoning_handling(self):
        """
        Req 13: Handles Gemini 2.5 reasoning models that emit thought parts
        alongside structured text responses without parse failures.
        """
        mock_reasoning_resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"thought": True, "text": "Analyzing the physical image for battery modules... Count appears to be 1."},
                            {"text": json.dumps({
                                "detected_items": [{"label": "EV_BATTERY_MODULE_6S2P", "count": 1, "confidence": 0.99}],
                                "estimated_item_count": 1,
                                "confidence": 0.99,
                                "material_estimates": {"Nickel": 4.14},
                                "notes": "One module identified after thinking."
                            })}
                        ]
                    }
                }
            ]
        }
        with patch.object(self.ai_service, "_call_gemini_api", return_value=mock_reasoning_resp):
            res = self.ai_service.observe(self.valid_jpeg_bytes, force_mode="LIVE_GEMINI")
            self.assertEqual(res.estimated_item_count, 1)
            self.assertEqual(res.confidence, 0.99)
            self.assertEqual(res.provenance, "AI_ESTIMATED")

    # -------------------------------------------------------------------------
    # 14. Oversized Evidence File Rejection (>20MB)
    # -------------------------------------------------------------------------
    def test_14_oversized_evidence_rejection(self):
        """
        Req 14: Oversized payloads exceeding the 20MB inline multimodal limit
        are cleanly rejected with GeminiImageRejectedError.
        """
        oversized_bytes = b"X" * (20 * 1024 * 1024 + 10)
        with self.assertRaises(GeminiImageRejectedError):
            self.ai_service.observe(oversized_bytes, force_mode="LIVE_GEMINI", allow_fallback=False)

    # -------------------------------------------------------------------------
    # 15. Live Gemini Failure Without Fallback
    # -------------------------------------------------------------------------
    def test_15_live_gemini_failure_without_fallback(self):
        """
        Req 15: When allow_fallback=False, a Gemini outage records ai_fallback_occurred=True,
        leaves ai_observation=None, and does NOT inject simulated fixture data.
        """
        fid = self._upload_test_image("strict_no_fall")
        pid = self._create_and_prep_passport("DPP-STRICT-FAIL")

        req = {
            "passport_id": pid,
            "intake_gross_mass_kg": 25.0,
            "claimed_materials": [{"material_name": "Nickel", "claimed_mass_kg": 4.14, "purity_pct": 99.0}],
            "evidence_file_ids": [fid],
            "run_ai_observation": True,
            "ai_force_mode": "LIVE_GEMINI",
            "allow_fallback": False,
        }

        with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-key"}):
            with patch("ml.inference.dual_mode_observer.DualModeAIObservationService._call_gemini_api",
                       side_effect=GeminiUnavailableError("GEMINI_UNAVAILABLE: HTTP 503")):
                res = self.client.post("/api/v1/custom-verification/verify", json=req)
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data["ai_fallback_occurred"])
                self.assertIsNone(data["ai_observation"])
                self.assertIn("GEMINI_UNAVAILABLE", data["ai_fallback_reason"])

    # -------------------------------------------------------------------------
    # 16. Frontend HTML Truthfulness Elements
    # -------------------------------------------------------------------------
    def test_16_frontend_html_truthfulness_elements(self):
        """
        Req 16: index.html contains truthful provenance labels, Evidence SHA-256 field,
        and no ambiguous Gemini 2.0 / Replayable Fixtures or hardcoded 40 Units baseline.
        """
        index_path = os.path.join(PROJECT_ROOT, "backend", "app", "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Check absence of ambiguous static placeholders
        self.assertNotIn("Gemini 2.0 / Replayable Fixtures", html)
        self.assertNotIn("40 Units (Baseline Replay)", html)

        # Check presence of audit SHA and failure rendering elements
        self.assertIn("ai-audit-sha", html)
        self.assertIn("Evidence SHA-256", html)
        self.assertIn("LIVE GEMINI — UNAVAILABLE", html)
        self.assertIn("FALLBACK → DETERMINISTIC FIXTURE", html)


if __name__ == "__main__":
    unittest.main()
