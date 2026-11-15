"""API v1 router aggregating all endpoints."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.detections import router as detections_router
from app.api.v1.documents import router as documents_router
from app.api.v1.personalization import router as personalization_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(detections_router)
api_v1_router.include_router(personalization_router)

__all__ = ["api_v1_router"]

