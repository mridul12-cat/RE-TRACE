"""
ml/inference/dual_mode_observer.py — Dual-Mode AI Observation Service.

Implements Section R3 and R5:
1. Live Gemini Multimodal API mode for live demonstrations.
2. Deterministic replayable offline fixture mode for reproducible testing.
3. Graceful degradation / fallback on API unavailability (Case I).
4. Strictly labels all outputs with ProvenanceCategory.AI_ESTIMATED (ADR-001 Pillar 1 & 3).
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timezone

from ml.models.vision_schemas import (
    AIObservationResult,
    DetectedItem,
    BoundingBox,
)
from shared.schemas.provenance import ProvenanceCategory

logger = logging.getLogger("retrace.ml")
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"


class DualModeAIObservationService:
    """
    Dual-Mode Computer Vision observation service for physical evidence inspection.
    """

    def __init__(self, default_mode: str = "AUTO", api_key: Optional[str] = None):
        self.default_mode = default_mode.upper()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._cached_fixtures: Dict[str, Dict[str, Any]] = {}
        self._load_fixtures()

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
        fixture_override: Optional[str] = None
    ) -> AIObservationResult:
        """
        Inspects physical evidence bytes and extracts item classifications,
        material estimates, and anomaly flags.
        """
        mode = (force_mode or self.default_mode).upper()
        if mode == "AUTO":
            mode = "LIVE_GEMINI" if self.api_key else "DETERMINISTIC_FIXTURE"

        if mode == "LIVE_GEMINI":
            try:
                return self._observe_gemini_live(file_bytes, filename, mime_type, product_id)
            except Exception as err:
                logger.warning(
                    f"Live Gemini API invocation failed ({err}). "
                    f"Gracefully degrading to DETERMINISTIC_FIXTURE (Case I fallback)."
                )
                return self._observe_fixture(
                    product_id=product_id,
                    fixture_override=fixture_override,
                    fallback_reason=f"Fallback from LIVE_GEMINI: {str(err)}"
                )

        return self._observe_fixture(product_id=product_id, fixture_override=fixture_override)

    def _observe_fixture(
        self,
        product_id: Optional[str] = None,
        fixture_override: Optional[str] = None,
        fallback_reason: Optional[str] = None
    ) -> AIObservationResult:
        """
        Deterministic offline replay of pre-computed physical inspection telemetry.
        """
        fixture = None
        if fixture_override and fixture_override in self._cached_fixtures:
            fixture = self._cached_fixtures[fixture_override]
        elif product_id and product_id in self._cached_fixtures:
            fixture = self._cached_fixtures[product_id]
        elif "FIXTURE-EV-NMC622-NORMAL" in self._cached_fixtures:
            fixture = self._cached_fixtures["FIXTURE-EV-NMC622-NORMAL"]
        else:
            # Hardcoded minimal fallback fixture
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
            provenance_category=ProvenanceCategory.AI_ESTIMATED,
            notes=notes
        )

    def _observe_gemini_live(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        product_id: Optional[str]
    ) -> AIObservationResult:
        """
        Invokes Google Gemini Multimodal Vision API when configured.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        import urllib.request
        import base64

        b64_data = base64.b64encode(file_bytes).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

        prompt = (
            "You are the computer vision observation layer for RE:TRACE circular economy platform. "
            "Examine this physical recycling evidence image (e.g. battery pack, weighbridge ticket, scrap lot). "
            "Extract: "
            "1. Detected item labels and estimated count. "
            "2. Visual gross mass estimate in kg. "
            "3. Physical anomalies if visible. "
            "4. Estimated recoverable elemental composition in kg. "
            "Respond ONLY with a JSON object matching this schema: "
            "{"
            "  \"items\": [{\"label\": string, \"count\": int, \"confidence\": float}],"
            "  \"estimated_item_count\": int,"
            "  \"estimated_gross_mass_kg\": float,"
            "  \"confidence\": float,"
            "  \"material_estimates\": {\"NI\": float, \"CO\": float, ...},"
            "  \"anomaly_flags\": [string],"
            "  \"notes\": string"
            "}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=10.0) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))

        text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)

        detected = [
            DetectedItem(
                label=it.get("label", "ITEM"),
                count=it.get("count", 1),
                confidence=float(it.get("confidence", 0.9))
            )
            for it in parsed.get("items", [])
        ]

        return AIObservationResult(
            provider="google-gemini",
            model="gemini-2.5-flash",
            execution_mode="LIVE_GEMINI",
            inference_timestamp=datetime.now(timezone.utc),
            detected_items=detected,
            material_estimates=parsed.get("material_estimates", {}),
            estimated_item_count=int(parsed.get("estimated_item_count", 1)),
            estimated_gross_mass_kg=float(parsed.get("estimated_gross_mass_kg", 0.0)),
            confidence=float(parsed.get("confidence", 0.95)),
            anomaly_flags=parsed.get("anomaly_flags", []),
            provenance_category=ProvenanceCategory.AI_ESTIMATED,
            notes=parsed.get("notes", "Live Gemini Multimodal visual inspection completed.")
        )
