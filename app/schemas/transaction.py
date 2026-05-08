"""Pydantic schemas for transactions — predicted, corrected, and API responses."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ConfidenceScores(BaseModel):
    date: float = 0.0
    description: float = 0.0
    amount: float = 0.0
    balance: float = 0.0


class TransactionBase(BaseModel):
    txn_date: Optional[str] = None
    value_date: Optional[str] = None
    description: str = ""
    reference_no: Optional[str] = None
    debit: Optional[float] = None
    credit: Optional[float] = None
    balance: Optional[float] = None
    txn_type: str = "unknown"
    currency: str = "INR"


class PredictedTransactionSchema(TransactionBase):
    id: uuid.UUID
    document_id: uuid.UUID
    sequence: int
    raw_text: str = ""
    confidence: Optional[ConfidenceScores] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None

    model_config = {"from_attributes": True}


class CorrectionRequest(BaseModel):
    """A single field-level correction."""
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class TransactionCorrectionRequest(BaseModel):
    """Correction for a single transaction row."""
    predicted_id: Optional[uuid.UUID] = None
    sequence: int
    correction_type: str = "field_edit"  # field_edit, row_add, row_delete, row_merge
    corrections: list[CorrectionRequest] = []

    # Full corrected values
    txn_date: Optional[str] = None
    value_date: Optional[str] = None
    description: str = ""
    reference_no: Optional[str] = None
    debit: Optional[float] = None
    credit: Optional[float] = None
    balance: Optional[float] = None
    txn_type: str = "unknown"
    currency: str = "INR"


class BulkCorrectionRequest(BaseModel):
    """Bulk correction submission for a document."""
    document_id: uuid.UUID
    transactions: list[TransactionCorrectionRequest]


class TransactionListResponse(BaseModel):
    document_id: uuid.UUID
    bank: Optional[str] = None
    status: str
    transactions: list[PredictedTransactionSchema]
    total: int


class ExtractionResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    bank_detected: Optional[str] = None
    total_pages: int = 0
    status: str
    transactions: list[PredictedTransactionSchema] = []
    transaction_count: int = 0

    # Drive Archival Response
    drive_file_id: Optional[str] = None
    web_view_link: Optional[str] = None
    upload_status: str = "pending"

