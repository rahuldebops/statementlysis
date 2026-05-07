"""API Router — assembles all route modules."""

from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.transactions import router as transactions_router
from app.api.models_api import router as models_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(documents_router)
api_router.include_router(transactions_router)
api_router.include_router(models_router)
