"""Document Service — orchestrates upload, storage, and extraction."""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import sha256_file, hash_password
from app.core.types import DocumentStatus
from app.core.exceptions import DuplicateDocumentError
from app.db.models import (
    Document, DocumentPage, TokenRecord, ExtractedLineRecord,
    PredictedTransaction,
)
from app.extraction.pipeline import ExtractionPipeline, ExtractionResult
from app.extraction.validator import TransactionValidator
from app.repositories.document_repo import DocumentRepository
from app.repositories.transaction_repo import TransactionRepository

logger = logging.getLogger(__name__)


class DocumentService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.txn_repo = TransactionRepository(session)
        self.pipeline = ExtractionPipeline()

    async def upload_and_extract(
        self,
        filename: str,
        file_bytes: bytes,
        password: Optional[str] = None,
    ) -> tuple[Document, ExtractionResult, list[PredictedTransaction]]:
        """Upload a PDF, store it, run extraction, persist results."""

        # 1. Compute hash and check for duplicates
        file_hash = sha256_file(file_bytes)

        # 2. Store PDF to disk
        storage_path = self._store_pdf(file_bytes, file_hash, filename)

        # 3. Create document record
        doc = Document(
            original_filename=filename,
            sha256_hash=file_hash,
            storage_path=str(storage_path),
            password_hash=hash_password(password) if password else None,
            status=DocumentStatus.UPLOADED.value,
        )
        doc = await self.doc_repo.create(doc)
        logger.info(f"Document created: {doc.id} ({filename})")

        # 4. Run extraction pipeline
        try:
            await self.doc_repo.update_status(doc.id, DocumentStatus.EXTRACTING.value)
            result = self.pipeline.run(storage_path, password=password)

            # 5. Persist extraction data
            predicted_records = await self._persist_extraction(doc, result)

            doc.status = DocumentStatus.PARSED.value
            doc.bank_id = result.bank_result.bank_id
            doc.total_pages = result.total_pages
            doc.statement_type = result.bank_result.statement_type.value

            # Link to the parser version used
            from sqlalchemy import select
            from app.db.models import ParserVersion
            stmt = select(ParserVersion.id).where(
                ParserVersion.bank_id == result.bank_result.bank_id,
                ParserVersion.version == result.parser_version
            )
            pv_id = (await self.session.execute(stmt)).scalar_one_or_none()
            doc.parser_version_id = pv_id

            doc.processed_at = datetime.utcnow()
            await self.session.flush()

            logger.info(
                f"Extraction complete: {result.transaction_count} transactions, "
                f"bank={result.bank_result.bank_id}"
            )
            return doc, result, predicted_records

        except Exception as e:
            doc.status = DocumentStatus.FAILED.value
            await self.session.flush()
            logger.error(f"Extraction failed for {doc.id}: {e}")
            raise

    async def get_document(self, doc_id: uuid.UUID) -> Optional[Document]:
        return await self.doc_repo.get_by_id(doc_id)

    async def list_documents(self, skip: int = 0, limit: int = 50) -> tuple[list[Document], int]:
        return await self.doc_repo.list_all(skip, limit)

    async def reprocess(self, doc_id: uuid.UUID, password: Optional[str] = None) -> tuple[Document, ExtractionResult]:
        """Reprocess an existing document with current parser/model versions."""
        doc = await self.doc_repo.get_by_id(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        # Clear old predictions
        await self.txn_repo.delete_predicted_by_document(doc_id)

        # Rerun pipeline
        result = self.pipeline.run(doc.storage_path, password=password)
        await self._persist_extraction(doc, result)

        doc.status = DocumentStatus.PARSED.value
        doc.bank_id = result.bank_result.bank_id
        doc.processed_at = datetime.utcnow()
        await self.session.flush()

        return doc, result

    def _store_pdf(self, file_bytes: bytes, file_hash: str, filename: str) -> Path:
        """Store PDF to disk using content-addressed storage."""
        ext = Path(filename).suffix or ".pdf"
        # Use hash prefix for directory sharding
        shard = file_hash[:4]
        target_dir = settings.pdf_storage_dir / shard
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{file_hash}{ext}"

        if not target_path.exists():
            target_path.write_bytes(file_bytes)
            logger.debug(f"PDF stored: {target_path}")

        return target_path

    async def _persist_extraction(self, doc: Document, result: ExtractionResult) -> list[PredictedTransaction]:
        """Persist all extraction artifacts to the database."""

        # Save pages, tokens, and lines
        for page_data in result.pages:
            page_record = DocumentPage(
                document_id=doc.id,
                page_number=page_data.page_number,
                width=page_data.width,
                height=page_data.height,
                raw_text=page_data.raw_text,
            )
            page_record = await self.doc_repo.save_page(page_record)

            # Save tokens
            token_records = [
                TokenRecord(
                    page_id=page_record.id,
                    text=token.text,
                    x0=token.x0, x1=token.x1,
                    y0=token.y0, y1=token.y1,
                    sequence=token.sequence,
                )
                for token in page_data.tokens
            ]
            if token_records:
                await self.doc_repo.save_tokens(token_records)

            # Save lines
            line_records = [
                ExtractedLineRecord(
                    page_id=page_record.id,
                    line_number=line.line_number,
                    tokens_json=[t.to_dict() for t in line.tokens],
                    raw_text=line.text,
                    y_center=line.y_center,
                )
                for line in page_data.lines
            ]
            if line_records:
                await self.doc_repo.save_lines(line_records)

        # Save predicted transactions
        predicted_records = []
        for txn in result.transactions:
            parsed_date = TransactionValidator.parse_date(txn.txn_date) if txn.txn_date else None
            parsed_vdate = TransactionValidator.parse_date(txn.value_date) if txn.value_date else None

            record = PredictedTransaction(
                document_id=doc.id,
                sequence=txn.sequence,
                txn_date=parsed_date,
                value_date=parsed_vdate,
                description=(txn.description or "")[:5000],
                reference_no=(txn.reference_no or "")[:1000] if txn.reference_no else None,
                debit=txn.debit,
                credit=txn.credit,
                balance=txn.balance,
                txn_type=txn.txn_type.value if hasattr(txn.txn_type, 'value') else str(txn.txn_type),
                currency=txn.currency,
                raw_text=(txn.raw_text or "")[:10000],
                confidence=txn.confidence.to_dict(),
                source_tokens=txn.source_tokens[:50] if txn.source_tokens else None,
                page_start=txn.page_start,
                page_end=txn.page_end,
            )
            predicted_records.append(record)

        if predicted_records:
            await self.txn_repo.save_predicted(predicted_records)
            
        return predicted_records
