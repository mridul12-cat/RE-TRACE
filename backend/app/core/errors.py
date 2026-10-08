"""
backend/app/core/errors.py — Standardized Exception Classes & HTTP Error Handling.
Prevents credential and secret leakage per Section R7.
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("retrace.errors")


class RETraceBaseError(Exception):
    """Base class for all RE:TRACE application domain exceptions."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, error_code: str = "ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ReplayDetectedError(RETraceBaseError):
    def __init__(self, message: str = "Replay detected: Identifier already recorded on ledger."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT, error_code="REPLAY_DETECTED")


class DuplicateCertificateError(RETraceBaseError):
    def __init__(self, message: str = "Duplicate certificate prohibited: Event already has an issued certificate."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT, error_code="DUPLICATE_CERTIFICATE_PROHIBITED")


class UnauthorizedTransitionError(RETraceBaseError):
    def __init__(self, message: str = "Actor role is not authorized to execute this lifecycle transition."):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN, error_code="UNAUTHORIZED_TRANSITION")


class IllegalTransitionError(RETraceBaseError):
    def __init__(self, message: str = "Illegal state transition attempted."):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, error_code="ILLEGAL_TRANSITION")


class EvidenceIntegrityError(RETraceBaseError):
    def __init__(self, message: str = "Evidence integrity verification failed (EVIDENCE_INTEGRITY_FAILURE)."):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, error_code="EVIDENCE_INTEGRITY_FAILURE")


class UnsupportedMediaTypeError(RETraceBaseError):
    def __init__(self, message: str = "Uploaded file MIME type is disallowed."):
        super().__init__(message, status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, error_code="UNSUPPORTED_MEDIA_TYPE")


class FileSizeLimitExceededError(RETraceBaseError):
    def __init__(self, message: str = "File size exceeds the maximum allowed 25MB limit."):
        super().__init__(message, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, error_code="FILE_TOO_LARGE")


class BlockchainOfflineError(RETraceBaseError):
    def __init__(self, message: str = "Blockchain RPC node is offline (LOCAL TESTNET unreachable)."):
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, error_code="BLOCKCHAIN_OFFLINE")


class ResourceNotFoundError(RETraceBaseError):
    def __init__(self, message: str = "Requested resource was not found."):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND, error_code="NOT_FOUND")


class GeminiError(RETraceBaseError):
    """Base exception for Google Gemini Multimodal Vision API operations."""
    def __init__(
        self,
        message: str = "Google Gemini inference error.",
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
        error_code: str = "GEMINI_ERROR"
    ):
        super().__init__(message, status_code=status_code, error_code=error_code)


class GeminiNotConfiguredError(GeminiError):
    def __init__(self, message: str = "GEMINI_NOT_CONFIGURED: GEMINI_API_KEY environment variable is not set."):
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, error_code="GEMINI_NOT_CONFIGURED")


class GeminiAuthError(GeminiError):
    def __init__(self, message: str = "GEMINI_AUTHENTICATION_FAILED: Gemini API key authentication failed."):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED, error_code="GEMINI_AUTHENTICATION_FAILED")


class GeminiRateLimitError(GeminiError):
    def __init__(self, message: str = "GEMINI_RATE_LIMITED: Gemini API rate limit or quota exceeded."):
        super().__init__(message, status_code=status.HTTP_429_TOO_MANY_REQUESTS, error_code="GEMINI_RATE_LIMITED")


class GeminiUnavailableError(GeminiError):
    def __init__(self, message: str = "GEMINI_UNAVAILABLE: Gemini API is temporarily unavailable."):
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, error_code="GEMINI_UNAVAILABLE")


class GeminiInvalidResponseError(GeminiError):
    def __init__(self, message: str = "GEMINI_INVALID_RESPONSE: Malformed or unparseable structured response from Gemini API."):
        super().__init__(message, status_code=status.HTTP_502_BAD_GATEWAY, error_code="GEMINI_INVALID_RESPONSE")


class GeminiImageRejectedError(GeminiError):
    def __init__(self, message: str = "GEMINI_IMAGE_REJECTED: Uploaded evidence content was rejected for multimodal inference."):
        super().__init__(message, status_code=422, error_code="GEMINI_IMAGE_REJECTED")


async def retrace_exception_handler(request: Request, exc: RETraceBaseError) -> JSONResponse:
    logger.warning(f"Domain exception on {request.method} {request.url.path}: {exc.error_code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "path": request.url.path,
        }
    )
