"""Training Repository — data access for training samples."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrainingSample


class TrainingRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_samples(self, samples: list[TrainingSample]) -> None:
        self.session.add_all(samples)
        await self.session.flush()

    async def get_by_document(self, doc_id: uuid.UUID) -> list[TrainingSample]:
        stmt = (
            select(TrainingSample)
            .where(TrainingSample.document_id == doc_id)
            .order_by(TrainingSample.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_bank(self, bank_id: str, limit: int = 1000) -> list[TrainingSample]:
        stmt = (
            select(TrainingSample)
            .where(TrainingSample.bank_id == bank_id)
            .order_by(TrainingSample.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_bank(self, bank_id: str) -> int:
        stmt = select(func.count()).select_from(TrainingSample).where(TrainingSample.bank_id == bank_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
