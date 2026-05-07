"""Pydantic schemas for extraction pipeline responses."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.schemas.token import TokenSchema, LineSchema


class PageExtractionResult(BaseModel):
    page_number: int
    width: float
    height: float
    token_count: int
    line_count: int


class ExtractionSummary(BaseModel):
    total_pages: int
    total_tokens: int
    total_lines: int
    bank_detected: Optional[str] = None
    bank_confidence: float = 0.0
    pages: list[PageExtractionResult] = []
