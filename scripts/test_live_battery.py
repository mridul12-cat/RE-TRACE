#!/usr/bin/env python3
"""
scripts/test_live_battery.py — Real Live Gemini Multimodal Battery Verification

Performs real live Gemini requests against gemini-3.8-flash using the uploaded
battery image (EV-FA773B255567), measuring request latency, units detected,
confidence, provider, and fallback status.
"""
import os
import sys
import glob
import time
from pathlib import Path

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

# Load .env if present
env_file = os.path.join(PROJECT_ROOT, ".env")
if os.path.isfile(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

from ml.inference.dual_mode_observer import DualModeAIObservationService


def run_battery_tests():
    api_key = os.getenv("GEMINI_API_KEY")
    svc = DualModeAIObservationService(default_mode="LIVE_GEMINI", api_key=api_key)
    print("=" * 70)
    print(" RE:TRACE — REAL LIVE GEMINI MULTIMODAL BATTERY TEST")
    print("=" * 70)
    print(f"Configured Timeout: {svc.current_timeout}s")
    print(f"Configured Model:   {svc.current_model}")
    print(f"API Key Present:    {bool(svc.current_api_key)}")

    image_path = os.path.join(
        PROJECT_ROOT, "backend", "data", "uploads",
        "EV-FA773B255567_whatsapp-image-2025-09-03-at-7-56-23-am-jpeg.jpeg"
    )
    if not os.path.exists(image_path):
        image_path = os.path.join(PROJECT_ROOT, "demo", "sample-images", "battery_module_pallet.jpg")
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    print(f"Target Image:       {os.path.basename(image_path)} ({len(image_bytes):,} bytes)")
    print("-" * 70)

    if not svc.current_api_key:
        print("[!] GEMINI_API_KEY is not set in environment or .env.")
        print("[!] Demonstrating truthful fallback behavior on unconfigured key:")
        obs_fallback = svc.observe(
            file_bytes=image_bytes,
            filename=os.path.basename(image_path),
            mime_type="image/jpeg",
            force_mode="LIVE_GEMINI",
            evidence_id="EV-FA773B255567",
            allow_fallback=True
        )
        print(f"  * Mode:       {obs_fallback.execution_mode}")
        print(f"  * Provider:   {obs_fallback.provider}")
        print(f"  * Provenance: {obs_fallback.provenance}")
        print(f"  * Notes:      {obs_fallback.notes[:120]}...")
        return

    # Request 1
    print("\n[+] Executing Request 1...")
    t0 = time.time()
    try:
        obs_1 = svc.observe(
            file_bytes=image_bytes,
            filename=os.path.basename(image_path),
            mime_type="image/jpeg",
            force_mode="LIVE_GEMINI",
            evidence_id="EV-FA773B255567",
            allow_fallback=True
        )
        lat_1 = time.time() - t0
        print(f"  * Latency:         {lat_1:.2f}s")
        print(f"  * Execution Mode:  {obs_1.execution_mode}")
        print(f"  * Provider:        {obs_1.provider}")
        print(f"  * Model:           {obs_1.model}")
        print(f"  * Observed Units:  {obs_1.estimated_item_count}")
        print(f"  * Confidence:      {obs_1.confidence:.1%}")
        print(f"  * Provenance:      {obs_1.provenance}")
        print(f"  * Fallback State:  {'FALLBACK' if obs_1.execution_mode != 'LIVE_GEMINI' else 'SUCCESS (LIVE)'}")
        if obs_1.execution_mode != "LIVE_GEMINI":
            print(f"  * Fallback Reason: {obs_1.notes}")
    except Exception as e:
        lat_1 = time.time() - t0
        print(f"  * Request 1 Failed ({lat_1:.2f}s): {e}")

    # Brief delay between requests to avoid rate limits
    time.sleep(2)

    # Request 2
    print("\n[+] Executing Request 2...")
    t0 = time.time()
    try:
        obs_2 = svc.observe(
            file_bytes=image_bytes,
            filename=os.path.basename(image_path),
            mime_type="image/jpeg",
            force_mode="LIVE_GEMINI",
            evidence_id="EV-FA773B255567",
            allow_fallback=True
        )
        lat_2 = time.time() - t0
        print(f"  * Latency:         {lat_2:.2f}s")
        print(f"  * Execution Mode:  {obs_2.execution_mode}")
        print(f"  * Provider:        {obs_2.provider}")
        print(f"  * Model:           {obs_2.model}")
        print(f"  * Observed Units:  {obs_2.estimated_item_count}")
        print(f"  * Confidence:      {obs_2.confidence:.1%}")
        print(f"  * Provenance:      {obs_2.provenance}")
        print(f"  * Fallback State:  {'FALLBACK' if obs_2.execution_mode != 'LIVE_GEMINI' else 'SUCCESS (LIVE)'}")
        if obs_2.execution_mode != "LIVE_GEMINI":
            print(f"  * Fallback Reason: {obs_2.notes}")
    except Exception as e:
        lat_2 = time.time() - t0
        print(f"  * Request 2 Failed ({lat_2:.2f}s): {e}")

    print("\n" + "=" * 70)
    print("Multimodal battery test completed.")
    print("=" * 70)


if __name__ == "__main__":
    run_battery_tests()
