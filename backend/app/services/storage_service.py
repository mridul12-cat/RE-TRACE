"""
backend/app/services/storage_service.py — Physical Evidence Storage & File Hasher.
Satisfies Section R2 and R7.
"""

import uuid
import hashlib
from typing import Tuple, Optional, Dict
from pathlib import Path
from datetime import datetime, timezone

from backend.app.core.config import settings
from backend.app.core.security import sniff_and_validate_file
from shared.schemas.evidence_bundle import EvidenceFileRecord
from shared.schemas.provenance import ProvenanceCategory


class StorageService:
    """Manages file storage and cryptographic hashing of uploaded evidence."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.upload_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, EvidenceFileRecord] = {}

    def store_evidence(
        self,
        content: bytes,
        filename: str,
        declared_mime: str,
        provenance_category: ProvenanceCategory = ProvenanceCategory.MEASURED,
        description: Optional[str] = None
    ) -> EvidenceFileRecord:
        """
        Validates MIME sniffing, computes SHA-256 digest, stores file to disk,
        and registers EvidenceFileRecord.
        """
        validated_mime, safe_name = sniff_and_validate_file(content, declared_mime, filename)
        file_id = f"EV-{uuid.uuid4().hex[:12].upper()}"
        sha256_digest = hashlib.sha256(content).hexdigest()

        # Save to disk using file_id prefix to avoid collision
        disk_filename = f"{file_id}_{safe_name}"
        file_path = self.base_dir / disk_filename
        file_path.write_bytes(content)

        record = EvidenceFileRecord(
            file_id=file_id,
            filename=safe_name,
            mime_type=validated_mime,
            file_size_bytes=len(content),
            sha256_hash=sha256_digest,
            provenance=provenance_category
        )
        self._index[file_id] = record
        return record

    def get_record(self, file_id: str) -> Optional[EvidenceFileRecord]:
        return self._index.get(file_id)

    def get_content(self, file_id: str) -> Optional[bytes]:
        record = self.get_record(file_id)
        if not record:
            return None
        disk_filename = f"{record.file_id}_{record.filename}"
        file_path = self.base_dir / disk_filename
        if file_path.exists():
            return file_path.read_bytes()
        return None

    def list_records(self) -> Dict[str, EvidenceFileRecord]:
        return dict(self._index)


storage_service = StorageService()
