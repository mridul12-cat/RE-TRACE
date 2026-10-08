"""
backend/app/main.py — FastAPI Application Entrypoint for RE:TRACE.
Digital Product Passport, Mass-Balance Verification & Cryptographic Ledger API.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from backend.app.core.config import settings
from backend.app.core.errors import RETraceBaseError, retrace_exception_handler
from backend.app.api.v1 import api_v1_router
from backend.app.services.blockchain_service import blockchain_service

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "RE:TRACE circular economy and climate tracking platform providing verifiable "
        "end-to-end digital product passport (DPP) traceability, dual-mode AI recycling "
        "observation, deterministic mass-balance verification, and blockchain lifecycle tracking."
    ),
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for Next.js frontend or local dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register domain exception handlers
app.add_exception_handler(RETraceBaseError, retrace_exception_handler)

# Include API v1 routers
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["System"])
def health_check():
    """System health check and circular ledger connection status."""
    return {
        "status": "HEALTHY",
        "service": "RE:TRACE API",
        "version": settings.app_version,
        "environment": settings.environment,
        "blockchain": blockchain_service.get_status(),
        "storage_upload_dir": str(settings.upload_dir),
    }


STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(STATIC_DIR), html=True), name="dashboard")


@app.get("/", tags=["System"])
def root_info(request: Request):
    """Welcome and metadata endpoint. Serves interactive dashboard for browser, JSON for API."""
    accept = request.headers.get("accept", "")
    index_file = STATIC_DIR / "index.html"
    if "text/html" in accept and index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "dashboard_url": "/dashboard",
        "docs_url": "/docs",
        "api_v1": settings.api_v1_prefix,
        "blockchain_label": settings.blockchain_network_label,
        "chain_id": settings.blockchain_chain_id,
        "status": "RUNNING"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
