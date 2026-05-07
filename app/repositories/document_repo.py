"""Document Repository — data access layer for documents and pages."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Document, DocumentPage, TokenRecord, ExtractedLineRecord


class DocumentRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_by_id(self, doc_id: uuid.UUID) -> Optional[Document]:
        stmt = (
            select(Document)
            .where(Document.id == doc_id)
            .options(selectinload(Document.pages))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_hash(self, sha256: str) -> Optional[Document]:
        stmt = select(Document).where(Document.sha256_hash == sha256)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 50) -> tuple[list[Document], int]:
        count_stmt = select(func.count()).select_from(Document)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(Document)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def update_status(self, doc_id: uuid.UUID, status: str) -> None:
        doc = await self.get_by_id(doc_id)
        if doc:
            doc.status = status
            await self.session.flush()

    async def save_page(self, page: DocumentPage) -> DocumentPage:
        self.session.add(page)
        await self.session.flush()
        return page

    async def save_tokens(self, tokens: list[TokenRecord]) -> None:
        self.session.add_all(tokens)
        await self.session.flush()

    async def save_lines(self, lines: list[ExtractedLineRecord]) -> None:
        self.session.add_all(lines)
        await self.session.flush()
