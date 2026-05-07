"""Transaction correction API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.correction_service import CorrectionService
from app.schemas.transaction import BulkCorrectionRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/confirm")
async def confirm_corrections(
    request: BulkCorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit corrected transactions for a document."""
    service = CorrectionService(db)

    try:
        corrected = await service.submit_corrections(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "status": "confirmed",
        "document_id": str(request.document_id),
        "corrected_count": len(corrected),
        "training_samples_generated": len(corrected),
    }
