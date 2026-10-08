"""
backend/app/api/v1/evidence.py — Physical Evidence Upload & Retrieval API Endpoints.
Enforces Section R2 and R7.
"""

from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Response
from shared.schemas.evidence_bundle import EvidenceFileRecord
from shared.schemas.provenance import ProvenanceCategory
from backend.app.services.storage_service import storage_service
from backend.app.core.errors import ResourceNotFoundError

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.post("/upload", response_model=EvidenceFileRecord, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    file: UploadFile = File(...),
    provenance_category: str = Form("MEASURED"),
    description: Optional[str] = Form(None)
):
    """
    Uploads physical evidence (image, weighbridge slip, analytical assay).
    Validates MIME sniffing and enforces 25MB file-size limit.
    Computes streaming SHA-256 hash.
    """
    content = await file.read()
    filename = file.filename or "evidence.bin"
    content_type = file.content_type or "application/octet-stream"

    # Map provenance category string
    try:
        prov = ProvenanceCategory(provenance_category.upper())
    except ValueError:
        prov = ProvenanceCategory.MEASURED

    record = storage_service.store_evidence(
        content=content,
        filename=filename,
        declared_mime=content_type,
        provenance_category=prov,
        description=description
    )
    return record


@router.get("/{file_id}", response_model=EvidenceFileRecord)
def get_evidence_record(file_id: str):
    """Retrieves metadata record for uploaded evidence."""
    record = storage_service.get_record(file_id)
    if not record:
        raise ResourceNotFoundError(f"Evidence file '{file_id}' not found.")
    return record


@router.get("/{file_id}/download")
def download_evidence(file_id: str):
    """Downloads raw bytes of uploaded evidence."""
    record = storage_service.get_record(file_id)
    if not record:
        raise ResourceNotFoundError(f"Evidence file '{file_id}' not found.")
    content = storage_service.get_content(file_id)
    if content is None:
        raise ResourceNotFoundError(f"Evidence file '{file_id}' content missing from disk.")

    return Response(
        content=content,
        media_type=record.mime_type,
        headers={"Content-Disposition": f'inline; filename="{record.filename}"'}
    )


@router.get("", response_model=List[EvidenceFileRecord])
def list_evidence():
    """Lists all stored evidence files."""
    return list(storage_service.list_records().values())
