"""
backend/app/core/config.py — Application Configuration & Environment Settings.
Strictly conforms to Section R5 and R7.
"""

import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _load_env_file():
    """Loads key-value pairs from .env into os.environ if not already defined."""
    env_file = WORKSPACE_ROOT / ".env"
    if env_file.is_file():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass


_load_env_file()


def _get_default_gemini_model() -> str:
    raw = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    if raw.startswith("models/"):
        raw = raw[len("models/"):].strip()
    return raw or "gemini-3.8-flash"


def _get_default_gemini_timeout() -> float:
    raw = os.getenv("GEMINI_TIMEOUT_SECONDS", "30.0").strip()
    try:
        val = float(raw)
        return max(5.0, min(60.0, val))
    except (ValueError, TypeError):
        return 30.0


class Settings(BaseModel):
    app_name: str = "RE:TRACE Circular Economy Verification Platform"
    app_version: str = "1.1.1"
    api_v1_prefix: str = "/api/v1"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "demo"))

    # Security & Storage
    upload_dir: Path = Field(
        default_factory=lambda: WORKSPACE_ROOT / "backend" / "data" / "uploads"
    )
    max_upload_size_bytes: int = 25 * 1024 * 1024  # 25 MB limit per R7
    allowed_mime_types: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    ]

    # Blockchain Truthfulness (Section R5)
    blockchain_network_label: str = "LOCAL TESTNET"
    blockchain_chain_id: int = 31337
    blockchain_rpc_url: str = Field(
        default_factory=lambda: os.getenv("RPC_URL", "http://127.0.0.1:8545")
    )

    # AI Configuration
    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    gemini_model: str = Field(
        default_factory=_get_default_gemini_model
    )
    gemini_timeout_seconds: float = Field(
        default_factory=_get_default_gemini_timeout
    )
    ai_mode: str = Field(
        default_factory=lambda: os.getenv("AI_MODE", "AUTO")
    )


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
