from fastapi import APIRouter

from backend.app.api.v1.passports import router as passports_router
from backend.app.api.v1.evidence import router as evidence_router
from backend.app.api.v1.recycling import router as recycling_router
from backend.app.api.v1.ai import router as ai_router
from backend.app.api.v1.verification import router as verification_router
from backend.app.api.v1.certificates import router as certificates_router
from backend.app.api.v1.lifecycle import router as lifecycle_router
from backend.app.api.v1.blockchain import router as blockchain_router
from backend.app.api.v1.demo import router as demo_router
from backend.app.api.v1.custom_verification import router as custom_verification_router

api_v1_router = APIRouter()
api_v1_router.include_router(passports_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(recycling_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(verification_router)
api_v1_router.include_router(certificates_router)
api_v1_router.include_router(lifecycle_router)
api_v1_router.include_router(blockchain_router)
api_v1_router.include_router(demo_router)
api_v1_router.include_router(custom_verification_router)

__all__ = ["api_v1_router"]
