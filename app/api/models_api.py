"""Model/Training API endpoints — placeholder for Phase 6."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.training_service import TrainingService

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/retrain")
async def retrain_model(db: AsyncSession = Depends(get_db)):
    """Trigger model retraining (Phase 6 placeholder)."""
    service = TrainingService(db)
    stats = await service.get_training_stats()
    return stats


@router.get("/training-data")
async def get_training_data(
    bank_id: str = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Export training data samples."""
    service = TrainingService(db)
    data = await service.export_training_data(bank_id=bank_id, limit=limit)
    return {"samples": data, "count": len(data)}
