"""Document API endpoints."""

from __future__ import annotations

import logging
import traceback
import uuid

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.document_service import DocumentService
from app.schemas.document import DocumentUploadResponse, DocumentListResponse, DocumentSummary
from app.schemas.transaction import (
    ExtractionResponse, PredictedTransactionSchema, TransactionListResponse,
    ConfidenceScores,
)
from app.core.exceptions import PDFPasswordRequired, PDFPasswordIncorrect, PDFExtractionError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/extract", response_model=ExtractionResponse)
async def upload_and_extract(
    file: UploadFile = File(...),
    password: str = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF and extract transactions."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    service = DocumentService(db)

    try:
        doc, result, predicted_records = await service.upload_and_extract(
            filename=file.filename,
            file_bytes=file_bytes,
            password=password,
        )
    except PDFPasswordRequired:
        raise HTTPException(status_code=422, detail="PDF is password-protected. Please provide a password.")
    except PDFPasswordIncorrect:
        raise HTTPException(status_code=422, detail="Incorrect PDF password.")
    except PDFExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Extraction failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)[:300]}")

    # Build response using real database IDs
    transactions = []
    for i, txn in enumerate(result.transactions):
        conf = txn.confidence
        db_record = predicted_records[i] if i < len(predicted_records) else None
        
        transactions.append(
            PredictedTransactionSchema(
                id=db_record.id if db_record else uuid.uuid4(),
                document_id=doc.id,
                sequence=txn.sequence,
                txn_date=txn.txn_date,
                value_date=txn.value_date,
                description=txn.description[:2000] if txn.description else "",
                reference_no=txn.reference_no[:500] if txn.reference_no else None,
                debit=txn.debit,
                credit=txn.credit,
                balance=txn.balance,
                txn_type=txn.txn_type.value if hasattr(txn.txn_type, 'value') else str(txn.txn_type),
                currency=txn.currency,
                raw_text=txn.raw_text[:2000] if txn.raw_text else "",
                confidence=ConfidenceScores(
                    date=conf.date,
                    description=conf.description,
                    amount=conf.amount,
                    balance=conf.balance,
                ) if conf else None,
            )
        )

    return ExtractionResponse(
        document_id=doc.id,
        filename=doc.original_filename,
        bank_detected=result.bank_result.bank_name,
        total_pages=result.total_pages,
        status=doc.status,
        transactions=transactions,
        transaction_count=len(transactions),
        drive_file_id=doc.drive_file_id,
        web_view_link=None, # We don't store it in DB currently, but doc.drive_file_id is there
        upload_status="success" if doc.drive_file_id else "failed"
    )



@router.get("", response_model=DocumentListResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded documents."""
    service = DocumentService(db)
    docs, total = await service.list_documents(skip, limit)

    return DocumentListResponse(
        documents=[
            DocumentSummary(
                id=d.id,
                original_filename=d.original_filename,
                status=d.status,
                bank_id=d.bank_id,
                total_pages=d.total_pages,
                created_at=d.created_at,
                processed_at=d.processed_at,
            )
            for d in docs
        ],
        total=total,
    )


@router.get("/{document_id}/transactions", response_model=TransactionListResponse)
async def get_transactions(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get extracted transactions for a document."""
    service = DocumentService(db)
    doc = await service.get_document(document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.repositories.transaction_repo import TransactionRepository
    txn_repo = TransactionRepository(db)
    predicted = await txn_repo.get_predicted_by_document(document_id)

    transactions = [
        PredictedTransactionSchema(
            id=p.id,
            document_id=p.document_id,
            sequence=p.sequence,
            txn_date=str(p.txn_date) if p.txn_date else None,
            value_date=str(p.value_date) if p.value_date else None,
            description=p.description,
            reference_no=p.reference_no,
            debit=float(p.debit) if p.debit else None,
            credit=float(p.credit) if p.credit else None,
            balance=float(p.balance) if p.balance else None,
            txn_type=p.txn_type,
            currency=p.currency,
            raw_text=p.raw_text,
        )
        for p in predicted
    ]

    return TransactionListResponse(
        document_id=document_id,
        bank=doc.bank_id,
        status=doc.status,
        transactions=transactions,
        total=len(transactions),
    )
