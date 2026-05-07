"""Core type definitions shared across the application."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    PARSING = "parsing"
    PARSED = "parsed"
    VALIDATED = "validated"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class TransactionType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    UNKNOWN = "unknown"


class CorrectionType(str, enum.Enum):
    FIELD_EDIT = "field_edit"
    ROW_ADD = "row_add"
    ROW_DELETE = "row_delete"
    ROW_MERGE = "row_merge"
    ROW_SPLIT = "row_split"


class StatementType(str, enum.Enum):
    SAVINGS = "savings"
    CURRENT = "current"
    CREDIT_CARD = "credit_card"
    WALLET = "wallet"
    PASSBOOK = "passbook"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BBox:
    """Bounding box for a token or region on the page."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Token:
    """Internal representation of a single text token with coordinates."""
    text: str
    x0: float
    x1: float
    y0: float
    y1: float
    page: int
    sequence: int = 0

    @property
    def bbox(self) -> BBox:
        return BBox(x0=self.x0, y0=self.y0, x1=self.x1, y1=self.y1)

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "x0": self.x0,
            "x1": self.x1,
            "y0": self.y0,
            "y1": self.y1,
            "page": self.page,
            "sequence": self.sequence,
        }


@dataclass
class ExtractedLine:
    """A reconstructed line from grouped tokens."""
    tokens: list[Token]
    page: int
    line_number: int
    y_center: float

    @property
    def text(self) -> str:
        return " ".join(t.text for t in self.tokens)

    @property
    def bbox(self) -> BBox:
        return BBox(
            x0=min(t.x0 for t in self.tokens),
            y0=min(t.y0 for t in self.tokens),
            x1=max(t.x1 for t in self.tokens),
            y1=max(t.y1 for t in self.tokens),
        )


@dataclass
class FieldConfidence:
    """Confidence scores per transaction field."""
    date: float = 0.0
    description: float = 0.0
    amount: float = 0.0
    balance: float = 0.0

    def to_dict(self) -> dict:
        return {
            "date": round(self.date, 4),
            "description": round(self.description, 4),
            "amount": round(self.amount, 4),
            "balance": round(self.balance, 4),
        }

    @property
    def overall(self) -> float:
        scores = [self.date, self.description, self.amount, self.balance]
        return sum(scores) / len(scores)


@dataclass
class RawTransaction:
    """A single extracted transaction before persistence."""
    txn_date: Optional[str] = None
    value_date: Optional[str] = None
    description: str = ""
    reference_no: Optional[str] = None
    debit: Optional[float] = None
    credit: Optional[float] = None
    balance: Optional[float] = None
    txn_type: TransactionType = TransactionType.UNKNOWN
    currency: str = "INR"
    raw_text: str = ""
    confidence: FieldConfidence = field(default_factory=FieldConfidence)
    source_tokens: list[dict] = field(default_factory=list)
    page_start: int = 0
    page_end: int = 0
    sequence: int = 0


@dataclass
class PageData:
    """All extracted data from a single PDF page."""
    page_number: int
    width: float
    height: float
    raw_text: str
    tokens: list[Token]
    lines: list[ExtractedLine] = field(default_factory=list)


@dataclass
class BankDetectionResult:
    """Result of bank detection from PDF content."""
    bank_id: Optional[str] = None
    bank_name: Optional[str] = None
    confidence: float = 0.0
    matched_patterns: list[str] = field(default_factory=list)
    statement_type: StatementType = StatementType.UNKNOWN
