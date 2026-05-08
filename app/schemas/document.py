"""Pydantic schemas for documents."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    sha256_hash: str
    status: str
    bank_detected: Optional[str] = None
    total_pages: Optional[int] = None
    transaction_count: int = 0

    model_config = {"from_attributes": True}


class DocumentSummary(BaseModel):
    id: uuid.UUID
    original_filename: str
    status: str
    bank_id: Optional[str] = None
    total_pages: Optional[int] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    drive_file_id: Optional[str] = None
    drive_uploaded_at: Optional[datetime] = None


    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    total: int
