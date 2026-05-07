"""Training Service — manages training data export and future model retraining."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.training_repo import TrainingRepository

logger = logging.getLogger(__name__)


class TrainingService:
    """Manages training data and future model retraining."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.training_repo = TrainingRepository(session)

    async def get_training_stats(self) -> dict:
        """Get training data statistics."""
        # Placeholder — will be expanded in Phase 6
        return {
            "status": "not_implemented",
            "message": "Model retraining is a Phase 6 feature",
        }

    async def export_training_data(self, bank_id: Optional[str] = None, limit: int = 1000) -> list[dict]:
        """Export training samples as serializable dicts."""
        if bank_id:
            samples = await self.training_repo.get_by_bank(bank_id, limit)
        else:
            samples = []  # TODO: Add get_all method

        return [
            {
                "id": str(s.id),
                "bank_id": s.bank_id,
                "input_features": s.input_features,
                "expected_output": s.expected_output,
                "token_context": s.token_context,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in samples
        ]
