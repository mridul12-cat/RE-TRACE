#!/usr/bin/env python3
"""
scripts/diagnose_and_run_gemini.py — Diagnose and verify Gemini API connectivity.
Conforms strictly to authentication and security constraints. Never prints the API key.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import glob
venv_patterns = [
    str(PROJECT_ROOT / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"),
    str(PROJECT_ROOT / ".venv" / "lib" / "python*" / "site-packages"),
]
for pat in venv_patterns:
    for matched_path in glob.glob(pat):
        if os.path.isdir(matched_path) and matched_path not in sys.path:
            sys.path.insert(0, matched_path)

# Step 6: Load .env in the SAME process
env_file = PROJECT_ROOT / ".env"
loaded_keys = 0
if env_file.is_file():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
                    loaded_keys += 1

from ml.inference.dual_mode_observer import DualModeAIObservationService

def run():
    svc = DualModeAIObservationService()

    api_key = svc.current_api_key
    gemini_key_present = bool(api_key and len(api_key.strip()) > 5)
    model = svc.current_model

    # Request construction details
    clean_model = model
    if clean_model.startswith("models/"):
        clean_model = clean_model[len("models/"):].strip()

    target_url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent"

    # Step 7: Test authentication with minimal text-only generateContent request first
    text_payload = {
        "contents": [
            {
                "parts": [{"text": "Respond strictly with valid JSON: {\"status\": \"ok\"}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    req_data = json.dumps(text_payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": (api_key or "").strip()
    }
    auth_header_present = bool(headers.get("x-goog-api-key"))

    req = urllib.request.Request(
        target_url,
        data=req_data,
        headers=headers,
        method="POST"
    )

    http_status = None
    response_latency = None

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=svc.current_timeout) as resp:
            latency = time.time() - t0
            http_status = resp.status
            response_latency = f"{latency:.2f}s"
            resp_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as http_err:
        latency = time.time() - t0
        http_status = http_err.code
        response_latency = f"{latency:.2f}s"
        try:
            body = http_err.read().decode("utf-8", errors="ignore")
            if api_key and api_key in body:
                body = body.replace(api_key, "[REDACTED]")
            print(f"HTTP Error Body: {body[:300]}")
        except Exception:
            pass
    except Exception as err:
        latency = time.time() - t0
        http_status = f"ERROR: {type(err).__name__}"
        response_latency = f"{latency:.2f}s"

    print("--- DIAGNOSTIC RESULTS ---")
    print(f"GEMINI_KEY_PRESENT={gemini_key_present}")
    print(f"MODEL={clean_model}")
    print(f"AUTH_HEADER_PRESENT={auth_header_present}")
    print(f"HTTP status={http_status}")
    print(f"response latency={response_latency}")

    # Step 8: If text call succeeded, test multimodal battery image
    if http_status == 200:
        print("\n--- MULTIMODAL BATTERY TEST ---")
        battery_path = PROJECT_ROOT / "backend" / "data" / "uploads" / "EV-FA773B255567_whatsapp-image-2025-09-03-at-7-56-23-am-jpeg.jpeg"
        if not battery_path.is_file():
            battery_path = PROJECT_ROOT / "demo" / "sample-images" / "battery_module_pallet.jpg"

        image_bytes = battery_path.read_bytes()
        t_mm_0 = time.time()
        try:
            obs = svc.observe(
                file_bytes=image_bytes,
                filename=battery_path.name,
                mime_type="image/jpeg",
                force_mode="LIVE_GEMINI",
                evidence_id="EV-FA773B255567",
                allow_fallback=False
            )
            lat_mm = time.time() - t_mm_0
            print(f"Multimodal Latency: {lat_mm:.2f}s")
            print(f"Execution Mode:     {obs.execution_mode}")
            print(f"Provider:           {obs.provider}")
            print(f"Model:              {obs.model}")
            print(f"Observed Units:     {obs.estimated_item_count}")
            print(f"Confidence:         {obs.confidence:.1%}")
            print(f"Provenance:         {obs.provenance}")
        except Exception as mm_err:
            lat_mm = time.time() - t_mm_0
            clean_err = str(mm_err)
            if api_key and api_key in clean_err:
                clean_err = clean_err.replace(api_key, "[REDACTED]")
            print(f"Multimodal Failed ({lat_mm:.2f}s): {type(mm_err).__name__}: {clean_err}")


if __name__ == "__main__":
    run()
