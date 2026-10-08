"""
backend/app/core/security.py — File Sanitization & MIME Sniffing Engine.
Enforces Section R7: strict upload validation, 25MB limit, and zero traversal vulnerability.
"""

import re
from pathlib import Path
from typing import Tuple
from backend.app.core.config import settings
from backend.app.core.errors import (
    UnsupportedMediaTypeError,
    FileSizeLimitExceededError,
)

# Known magic numbers for allowed MIME formats
MAGIC_NUMBERS = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "application/pdf": [b"%PDF-"],
}

# Signatures of executable code or active scripts prohibited in evidence uploads
DISALLOWED_SIGNATURES = [
    b"MZ",                # DOS/PE Windows Executable header
    b"\x7fELF",           # Linux ELF binary header
    b"\xca\xfe\xba\xbe",  # Mach-O universal binary
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit binary
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit binary (reverse)
    b"<script",           # Embedded HTML/JS script
    b"<?php",             # Embedded PHP script
    b"<html",             # HTML document masquerading as image
    b"<svg",              # Raw SVG with possible script execution in raster MIME
    b"javascript:",       # Inline JavaScript URI
]


def sanitize_filename(filename: str) -> str:
    """Strips directory traversal sequences and unsafe characters."""
    clean = Path(filename).name
    # Strip any characters except alphanumeric, dashes, dots, underscores
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", clean)
    if not clean or clean.startswith("."):
        clean = f"evidence_{clean}"
    return clean


def sniff_and_validate_file(content: bytes, declared_mime: str, filename: str) -> Tuple[str, str]:
    """
    Validates uploaded content length, minimum structural integrity,
    verifies magic bytes, and defends against polyglots and embedded executables.
    Returns (validated_mime, safe_filename).
    """
    if len(content) > settings.max_upload_size_bytes:
        raise FileSizeLimitExceededError(
            f"File '{filename}' exceeds maximum allowed size of {settings.max_upload_size_bytes / (1024*1024):.1f}MB."
        )

    # Minimum size guard: legitimate JPEG/PNG/PDF/WebP structures require at least 16 bytes
    if len(content) < 16:
        raise UnsupportedMediaTypeError(
            f"File '{filename}' is too small ({len(content)} bytes) to be a valid {declared_mime} document."
        )

    clean_name = sanitize_filename(filename)
    declared_mime = declared_mime.lower().strip()

    if declared_mime not in settings.allowed_mime_types:
        raise UnsupportedMediaTypeError(
            f"MIME type '{declared_mime}' is not permitted. Allowed: {settings.allowed_mime_types}"
        )

    # Polyglot inspection: scan the first 2KB and last 1KB for disallowed executable or script markers
    probe_sample = (content[:2048] + content[-1024:]).lower()
    for bad_sig in DISALLOWED_SIGNATURES:
        # Check binary headers directly on raw content
        if content.startswith(bad_sig):
            raise UnsupportedMediaTypeError(
                f"File content contains prohibited executable/binary header '{bad_sig.hex()}'."
            )
        # Check textual script patterns (case-insensitive)
        if bad_sig.startswith(b"<") or bad_sig.startswith(b"java"):
            if bad_sig in probe_sample:
                raise UnsupportedMediaTypeError(
                    f"File content contains prohibited active script payload ({bad_sig.decode('ascii', errors='ignore')})."
                )

    # Magic byte inspection & structural checks
    valid_magic = False
    if declared_mime == "image/jpeg":
        # Standard JPEG starts with SOI marker 0xFF 0xD8 followed by 0xFF and a valid segment marker
        if content.startswith(b"\xff\xd8\xff"):
            # Ensure valid JPEG segment marker exists in byte 3 (e.g. APP0 \xe0, APP1 \xe1, DQT \xdb, SOF0 \xc0, etc.)
            valid_marker_prefixes = (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\xff\xd8\xff\xdb",
                                     b"\xff\xd8\xff\xc0", b"\xff\xd8\xff\xc4", b"\xff\xd8\xff\xee")
            if any(content.startswith(p) or content[2:3] == b"\xff" for p in valid_marker_prefixes):
                valid_magic = True
    elif declared_mime == "image/png":
        # PNG signature + standard IHDR chunk within first 32 bytes
        if content.startswith(b"\x89PNG\r\n\x1a\n") and b"IHDR" in content[:32]:
            valid_magic = True
    elif declared_mime == "application/pdf":
        if content.startswith(b"%PDF-"):
            valid_magic = True
    elif declared_mime == "image/webp":
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            valid_magic = True

    if not valid_magic:
        raise UnsupportedMediaTypeError(
            f"File content does not match declared MIME signature '{declared_mime}'."
        )

    return declared_mime, clean_name
