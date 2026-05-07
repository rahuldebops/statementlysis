"""Transaction Repository — data access for predicted and corrected transactions."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PredictedTransaction, CorrectedTransaction


class TransactionRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_predicted(self, transactions: list[PredictedTransaction]) -> None:
        self.session.add_all(transactions)
        await self.session.flush()

    async def get_predicted_by_document(self, doc_id: uuid.UUID) -> list[PredictedTransaction]:
        stmt = (
            select(PredictedTransaction)
            .where(PredictedTransaction.document_id == doc_id)
            .order_by(PredictedTransaction.sequence)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_predicted_by_id(self, txn_id: uuid.UUID) -> Optional[PredictedTransaction]:
        stmt = select(PredictedTransaction).where(PredictedTransaction.id == txn_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_predicted_by_document(self, doc_id: uuid.UUID) -> int:
        stmt = delete(PredictedTransaction).where(PredictedTransaction.document_id == doc_id)
        result = await self.session.execute(stmt)
        return result.rowcount

    async def save_corrected(self, transactions: list[CorrectedTransaction]) -> None:
        self.session.add_all(transactions)
        await self.session.flush()

    async def get_corrected_by_document(self, doc_id: uuid.UUID) -> list[CorrectedTransaction]:
        stmt = (
            select(CorrectedTransaction)
            .where(CorrectedTransaction.document_id == doc_id)
            .order_by(CorrectedTransaction.sequence)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_corrected_by_document(self, doc_id: uuid.UUID) -> int:
        stmt = delete(CorrectedTransaction).where(CorrectedTransaction.document_id == doc_id)
        result = await self.session.execute(stmt)
        return result.rowcount
