"""
ml/inference/dual_mode_observer.py — Dual-Mode AI Observation Service.

Implements Section R3 and R5:
1. Live Gemini Multimodal API mode for physical evidence inspection.
2. Deterministic replayable offline fixture mode for reproducible testing.
3. Explicit, auditable fallback on API unavailability with SIMULATED provenance.
4. Truthful provenance attribution: AI_ESTIMATED for live Gemini, SIMULATED for fixtures.
5. Strict trust boundary: AI observes evidence; deterministic verification makes decisions.
"""

import os
import re
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timezone

from ml.models.vision_schemas import (
    AIObservationResult,
    DetectedItem,
    BoundingBox,
)
from shared.schemas.provenance import ProvenanceCategory

try:
    from backend.app.core.errors import (
        GeminiError,
        GeminiNotConfiguredError,
        GeminiAuthError,
        GeminiRateLimitError,
        GeminiUnavailableError,
        GeminiInvalidResponseError,
        GeminiImageRejectedError,
    )
except ImportError:
    class GeminiError(Exception): pass
    class GeminiNotConfiguredError(GeminiError): pass
    class GeminiAuthError(GeminiError): pass
    class GeminiRateLimitError(GeminiError): pass
    class GeminiUnavailableError(GeminiError): pass
    class GeminiInvalidResponseError(GeminiError): pass
    class GeminiImageRejectedError(GeminiError): pass

logger = logging.getLogger("retrace.ml")
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"

SUPPORTED_GEMINI_MIMES = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/pdf",
]


class DualModeAIObservationService:
    """
    Dual-Mode Computer Vision observation service for physical evidence inspection.
    """

    def __init__(
        self,
        default_mode: str = "AUTO",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.default_mode = default_mode.upper()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._explicit_model = model
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self._cached_fixtures: Dict[str, Dict[str, Any]] = {}
        self._load_fixtures()

    @property
    def current_api_key(self) -> Optional[str]:
        """Resolves active Gemini API key from instance or environment."""
        return self.api_key or os.getenv("GEMINI_API_KEY") or None

    @property
    def current_model(self) -> str:
        """Resolves active Gemini model identifier from environment, instance, or default."""
        env_model = os.getenv("GEMINI_MODEL")
        if env_model and env_model.strip():
            raw_model = env_model.strip()
        elif self._explicit_model and self._explicit_model.strip():
            raw_model = self._explicit_model.strip()
        else:
            raw_model = (self.model or "gemini-3.8-flash").strip()

        if raw_model.startswith("models/"):
            raw_model = raw_model[len("models/"):].strip()
        return raw_model or "gemini-3.8-flash"

    def _load_fixtures(self):
        if not FIXTURES_DIR.exists():
            return
        for fixture_file in FIXTURES_DIR.glob("*.json"):
            try:
                with open(fixture_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    fixture_id = data.get("fixture_id", fixture_file.stem)
                    self._cached_fixtures[fixture_id] = data
                    prod_id = data.get("product_id")
                    if prod_id and prod_id not in self._cached_fixtures:
                        self._cached_fixtures[prod_id] = data
            except Exception as e:
                logger.warning(f"Failed to load fixture {fixture_file}: {e}")

    def observe(
        self,
        file_bytes: bytes,
        filename: str = "evidence.jpg",
        mime_type: str = "image/jpeg",
        product_id: Optional[str] = None,
        force_mode: Optional[str] = None,
        fixture_override: Optional[str] = None,
        evidence_id: Optional[str] = None,
        evidence_sha256: Optional[str] = None,
        allow_fallback: bool = True,
    ) -> AIObservationResult:
        """
        Inspects physical evidence bytes and extracts item classifications,
        material estimates, and anomaly flags.
        """
        mode = (force_mode or self.default_mode).upper()
        if mode == "AUTO":
            mode = "LIVE_GEMINI" if self.current_api_key else "DETERMINISTIC_FIXTURE"

        if mode == "LIVE_GEMINI":
            try:
                if not self.current_api_key:
                    raise GeminiNotConfiguredError(
                        "GEMINI_NOT_CONFIGURED: GEMINI_API_KEY environment variable is not set."
                    )

                if not file_bytes or len(file_bytes) < 16:
                    raise GeminiImageRejectedError(
                        "GEMINI_IMAGE_REJECTED: Uploaded evidence content is empty or corrupt."
                    )

                return self._observe_gemini_live(
                    file_bytes=file_bytes,
                    filename=filename,
                    mime_type=mime_type,
                    product_id=product_id,
                    evidence_id=evidence_id,
                    evidence_sha256=evidence_sha256,
                )
            except Exception as err:
                safe_err_msg = str(err)
                curr_key = self.current_api_key
                if curr_key and curr_key in safe_err_msg:
                    safe_err_msg = safe_err_msg.replace(curr_key, "[REDACTED]")

                logger.warning(
                    f"Live Gemini API invocation failed ({safe_err_msg}). "
                    f"Gracefully degrading to DETERMINISTIC_FIXTURE (Case I fallback)."
                )

                if not allow_fallback:
                    raise

                return self._observe_fixture(
                    product_id=product_id,
                    fixture_override=fixture_override,
                    fallback_reason=f"Fallback from LIVE_GEMINI: {safe_err_msg}",
                    evidence_id=evidence_id,
                    evidence_sha256=evidence_sha256,
                )

        return self._observe_fixture(
            product_id=product_id,
            fixture_override=fixture_override,
            evidence_id=evidence_id,
            evidence_sha256=evidence_sha256,
        )

    def _observe_fixture(
        self,
        product_id: Optional[str] = None,
        fixture_override: Optional[str] = None,
        fallback_reason: Optional[str] = None,
        evidence_id: Optional[str] = None,
        evidence_sha256: Optional[str] = None,
    ) -> AIObservationResult:
        """
        Deterministic offline replay of pre-computed physical inspection telemetry.
        Strictly tagged with SIMULATED provenance.
        """
        fixture = None
        if fixture_override and fixture_override in self._cached_fixtures:
            fixture = self._cached_fixtures[fixture_override]
        elif product_id and product_id in self._cached_fixtures:
            fixture = self._cached_fixtures[product_id]
        elif "FIXTURE-EV-NMC622-NORMAL" in self._cached_fixtures:
            fixture = self._cached_fixtures["FIXTURE-EV-NMC622-NORMAL"]
        else:
            # Hardcoded baseline fixture
            fixture = {
                "provider": "deterministic-replay",
                "model": "retract-cv-nmc622-v1",
                "execution_mode": "DETERMINISTIC_FIXTURE",
                "detected_items": [
                    {"label": "EV_BATTERY_MODULE_6S2P", "count": 40, "confidence": 0.96}
                ],
                "estimated_item_count": 40,
                "estimated_gross_mass_kg": 1000.0,
                "confidence": 0.96,
                "material_estimates": {
                    "NI": 165.6,
                    "CO": 55.8,
                    "MN": 52.8,
                    "LI": 21.0,
                    "CU": 105.3,
                    "AL": 140.8
                },
                "anomaly_flags": [],
                "notes": "Offline deterministic baseline fixture."
            }

        detected = []
        for it in fixture.get("detected_items", []):
            bbox = None
            if "bounding_box" in it and it["bounding_box"]:
                bbox = BoundingBox(**it["bounding_box"])
            detected.append(
                DetectedItem(
                    label=it["label"],
                    count=it.get("count", 1),
                    confidence=it.get("confidence", 0.9),
                    bounding_box=bbox
                )
            )

        notes = fixture.get("notes")
        if fallback_reason:
            notes = f"[{fallback_reason}] {notes or ''}"

        return AIObservationResult(
            provider=fixture.get("provider", "deterministic-replay"),
            model=fixture.get("model", "retract-cv-v1"),
            execution_mode="DETERMINISTIC_FIXTURE",
            inference_timestamp=datetime.now(timezone.utc),
            detected_items=detected,
            material_estimates=fixture.get("material_estimates", {}),
            estimated_item_count=fixture.get("estimated_item_count", 1),
            estimated_gross_mass_kg=fixture.get("estimated_gross_mass_kg", 0.0),
            confidence=fixture.get("confidence", 0.95),
            anomaly_flags=fixture.get("anomaly_flags", []),
            provenance="SIMULATED",
            provenance_category=ProvenanceCategory.AI_ESTIMATED,
            evidence_id=evidence_id,
            evidence_sha256=evidence_sha256,
            notes=notes
        )

    def _call_gemini_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes HTTP POST request to Google Gemini Multimodal API.
        Passes API key securely via x-goog-api-key header (never in URL or query).
        Maps HTTP status codes to standardized domain exceptions.
        """
        import urllib.request
        import urllib.error

        api_key = (self.current_api_key or "").strip()
        if not api_key:
            raise GeminiNotConfiguredError(
                "GEMINI_NOT_CONFIGURED: GEMINI_API_KEY environment variable is not set."
            )

        clean_model = self.current_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent"

        # Sanitize payload: normalize any inline_data aliases to Google REST inlineData format
        outbound_payload = json.loads(json.dumps(payload))
        try:
            for c in outbound_payload.get("contents", []):
                for p in c.get("parts", []):
                    if "inline_data" in p:
                        if "inlineData" not in p:
                            id_data = p["inline_data"]
                            p["inlineData"] = {
                                "mimeType": id_data.get("mimeType") or id_data.get("mime_type"),
                                "data": id_data.get("data")
                            }
                        del p["inline_data"]
                    if "inlineData" in p:
                        id_data = p["inlineData"]
                        if "mime_type" in id_data and "mimeType" not in id_data:
                            id_data["mimeType"] = id_data.pop("mime_type")
        except Exception:
            pass

        req_data = json.dumps(outbound_payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                resp_bytes = resp.read()
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as http_err:
            code = http_err.code
            try:
                err_body = http_err.read().decode("utf-8", errors="ignore")
                if api_key and api_key in err_body:
                    err_body = err_body.replace(api_key, "[REDACTED]")
            except Exception:
                err_body = ""

            if code in (401, 403):
                raise GeminiAuthError(
                    f"GEMINI_AUTHENTICATION_FAILED: Google Gemini API rejected credentials (HTTP {code})."
                ) from http_err
            elif code == 429:
                raise GeminiRateLimitError(
                    "GEMINI_RATE_LIMITED: Google Gemini API quota or rate limit exceeded (HTTP 429)."
                ) from http_err
            elif code == 400:
                raise GeminiInvalidResponseError(
                    f"GEMINI_INVALID_RESPONSE: Google Gemini rejected request payload (HTTP 400): {err_body[:120]}."
                ) from http_err
            elif code == 404:
                body_suffix = f": {err_body[:160]}" if err_body else ""
                raise GeminiUnavailableError(
                    f"GEMINI_UNAVAILABLE: Configured Gemini model '{clean_model}' was not found or is unavailable (HTTP 404){body_suffix}."
                ) from http_err
            elif code in (500, 502, 503, 504):
                raise GeminiUnavailableError(
                    f"GEMINI_UNAVAILABLE: Google Gemini API is temporarily unavailable (HTTP {code})."
                ) from http_err
            else:
                body_suffix = f": {err_body[:160]}" if err_body else ""
                raise GeminiUnavailableError(
                    f"GEMINI_UNAVAILABLE: Unexpected response from Gemini API (HTTP {code}){body_suffix}."
                ) from http_err
        except (urllib.error.URLError, TimeoutError, OSError) as net_err:
            raise GeminiUnavailableError(
                f"GEMINI_UNAVAILABLE: Connection failure or timeout contacting Gemini API: {type(net_err).__name__}."
            ) from net_err

    def request_text(self, prompt: str) -> str:
        """
        Executes a minimal text-only Gemini request using the configured model.
        Useful for connectivity verification, health-checks, and minimal testing.
        """
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
            }
        }
        resp = self._call_gemini_api(payload)
        candidates = resp.get("candidates", [])
        if not candidates:
            feedback = resp.get("promptFeedback", {})
            raise GeminiInvalidResponseError(
                f"GEMINI_INVALID_RESPONSE: No candidate returned by Gemini API (feedback: {feedback})."
            )
        cand = candidates[0]
        finish_reason = cand.get("finishReason")
        if finish_reason and finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST"):
            raise GeminiInvalidResponseError(
                f"GEMINI_INVALID_RESPONSE: Model output blocked by safety policy (finishReason: {finish_reason})."
            )
        parts = cand.get("content", {}).get("parts", [])
        if not parts:
            raise GeminiInvalidResponseError(
                "GEMINI_INVALID_RESPONSE: Empty parts in Gemini candidate response."
            )
        text_parts = [
            p["text"] for p in parts
            if not p.get("thought") and "text" in p and p["text"]
        ]
        text = "\n".join(text_parts) if text_parts else parts[-1].get("text", "")
        return text.strip()

    def _observe_gemini_live(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        product_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        evidence_sha256: Optional[str] = None,
    ) -> AIObservationResult:
        """
        Sends the uploaded physical evidence image to the Google Gemini Multimodal API.
        Extracts structured observations without fixture substitution.
        """
        import base64

        if len(file_bytes) > 20 * 1024 * 1024:
            raise GeminiImageRejectedError(
                f"GEMINI_IMAGE_REJECTED: Uploaded evidence file size ({len(file_bytes)} bytes) exceeds 20MB multimodal limit."
            )

        effective_mime = mime_type.lower().strip()
        if effective_mime not in SUPPORTED_GEMINI_MIMES:
            if effective_mime.startswith("image/"):
                effective_mime = "image/jpeg"
            else:
                raise GeminiImageRejectedError(
                    f"GEMINI_IMAGE_REJECTED: Unsupported MIME type '{mime_type}' for multimodal vision."
                )

        b64_data = base64.b64encode(file_bytes).decode("utf-8")

        prompt = (
            "You are the physical evidence observation engine for RE:TRACE, a circular economy verification platform.\n"
            "Analyze the provided physical evidence image (such as an EV battery pack, module, cells, weighbridge scale ticket, or scrap metal lot).\n"
            "Carefully count the visible units or items in the image.\n"
            "Extract and return a strictly structured JSON object matching this schema:\n"
            "{\n"
            '  "detected_items": [{"label": string, "count": integer, "confidence": float}],\n'
            '  "estimated_item_count": integer,\n'
            '  "estimated_gross_mass_kg": float,\n'
            '  "confidence": float,\n'
            '  "material_estimates": {"Nickel": float, "Cobalt": float, "Lithium": float, "Manganese": float, "Copper": float, "Aluminum": float},\n'
            '  "anomaly_flags": [string],\n'
            '  "notes": string\n'
            "}\n"
            "Respond ONLY with valid JSON. Do not include introductory text or markdown formatting beyond JSON."
        )

        img_part = {
            "inlineData": {
                "mimeType": effective_mime,
                "data": b64_data
            },
            # Backward-compatible alias for test harness mocks
            "inline_data": {
                "mime_type": effective_mime,
                "data": b64_data
            }
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        img_part
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        resp_data = self._call_gemini_api(payload)

        try:
            candidates = resp_data.get("candidates", [])
            if not candidates:
                feedback = resp_data.get("promptFeedback", {})
                raise GeminiInvalidResponseError(
                    f"GEMINI_INVALID_RESPONSE: No candidate returned by Gemini API (feedback: {feedback})."
                )

            cand = candidates[0]
            finish_reason = cand.get("finishReason")
            if finish_reason and finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST"):
                raise GeminiInvalidResponseError(
                    f"GEMINI_INVALID_RESPONSE: Model output blocked by safety policy (finishReason: {finish_reason})."
                )

            parts = cand.get("content", {}).get("parts", [])
            if not parts:
                raise GeminiInvalidResponseError(
                    "GEMINI_INVALID_RESPONSE: Empty parts in Gemini candidate response."
                )

            # Filter out reasoning/thought parts (e.g. Gemini 2.5/3.8 thinking) to isolate text payload
            non_thought_parts = [
                p["text"] for p in parts
                if not p.get("thought") and "text" in p and p["text"]
            ]
            text = "\n".join(non_thought_parts) if non_thought_parts else parts[-1].get("text", "").strip()

            # Clean markdown code block wraps if present (including preambles)
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if fence_match:
                clean_text = fence_match.group(1).strip()
            else:
                clean_text = text.strip()

            try:
                parsed = json.loads(clean_text)
            except Exception:
                start_idx = text.find("{")
                end_idx = text.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    parsed = json.loads(text[start_idx : end_idx + 1])
                else:
                    raise
        except (GeminiInvalidResponseError, GeminiError):
            raise
        except Exception as parse_err:
            raise GeminiInvalidResponseError(
                f"GEMINI_INVALID_RESPONSE: Failed to parse structured JSON from Gemini response: {parse_err}"
            ) from parse_err

        # Extract items
        raw_items = parsed.get("detected_items") or parsed.get("items") or []
        detected = []
        for it in raw_items:
            bbox = None
            if "bounding_box" in it and it["bounding_box"]:
                try:
                    bbox = BoundingBox(**it["bounding_box"])
                except Exception:
                    bbox = None
            label_val = str(it.get("label") or it.get("item_name") or it.get("name") or "ITEM")
            count_val = max(1, int(it.get("count") or it.get("quantity") or 1))
            try:
                conf_val = min(1.0, max(0.0, float(it.get("confidence", 0.90))))
            except (ValueError, TypeError):
                conf_val = 0.90

            detected.append(
                DetectedItem(
                    label=label_val,
                    count=count_val,
                    confidence=conf_val,
                    bounding_box=bbox
                )
            )

        # Item count
        raw_count = parsed.get("estimated_item_count")
        if raw_count is None:
            raw_count = parsed.get("estimated_items")
        if raw_count is None:
            raw_count = parsed.get("unit_count")

        if raw_count is not None:
            try:
                est_count = max(0, int(raw_count))
            except (ValueError, TypeError):
                est_count = sum(d.count for d in detected) if detected else 1
        else:
            est_count = sum(d.count for d in detected) if detected else 1

        # Confidence - preserve model reported confidence without fabricating
        raw_conf = parsed.get("confidence")
        if raw_conf is not None:
            try:
                conf = min(1.0, max(0.0, float(raw_conf)))
            except (ValueError, TypeError):
                conf = 0.90
        elif detected:
            conf = sum(d.confidence for d in detected) / len(detected)
        else:
            conf = 0.85

        # Material estimates
        raw_materials = parsed.get("material_estimates") or {}
        mat_estimates: Dict[str, float] = {}
        if isinstance(raw_materials, dict):
            for k, v in raw_materials.items():
                try:
                    mat_estimates[str(k)] = float(v)
                except (ValueError, TypeError):
                    pass

        # Gross mass
        try:
            gross_mass = float(parsed.get("estimated_gross_mass_kg", 0.0))
        except (ValueError, TypeError):
            gross_mass = 0.0

        # Anomalies
        raw_anomalies = parsed.get("anomaly_flags") or []
        anomalies = [str(a) for a in raw_anomalies if a]

        # Notes
        notes = parsed.get("notes") or f"Live Gemini multimodal observation: {est_count} units detected."

        return AIObservationResult(
            provider="google-gemini",
            model=self.current_model,
            execution_mode="LIVE_GEMINI",
            inference_timestamp=datetime.now(timezone.utc),
            detected_items=detected,
            material_estimates=mat_estimates,
            estimated_item_count=est_count,
            estimated_gross_mass_kg=gross_mass,
            confidence=conf,
            anomaly_flags=anomalies,
            provenance="AI_ESTIMATED",
            provenance_category=ProvenanceCategory.AI_ESTIMATED,
            evidence_id=evidence_id,
            evidence_sha256=evidence_sha256,
            notes=str(notes)
        )
