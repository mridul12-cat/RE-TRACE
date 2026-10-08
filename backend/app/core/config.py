"""
backend/app/core/config.py — Application Configuration & Environment Settings.
Strictly conforms to Section R5 and R7.
"""

import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent


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
    ai_mode: str = Field(
        default_factory=lambda: os.getenv("AI_MODE", "AUTO")
    )


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
