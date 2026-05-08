"""SQLAlchemy ORM models — normalized schema for the extraction platform."""

from __future__ import annotations

import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, Date,
    Numeric, ForeignKey, UniqueConstraint, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.utcnow()


# ─── Banks ───────────────────────────────────────────────────────────────────

class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g. "hdfc", "sbi"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    detection_patterns: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Relationships
    documents: Mapped[list[Document]] = relationship(back_populates="bank")
    parser_versions: Mapped[list[ParserVersion]] = relationship(back_populates="bank")


# ─── Parser Versions ────────────────────────────────────────────────────────

class ParserVersion(Base):
    __tablename__ = "parser_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    bank_id: Mapped[str] = mapped_column(String(50), ForeignKey("banks.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    parser_class: Mapped[str] = mapped_column(String(300), nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (
        UniqueConstraint("bank_id", "version", name="uq_parser_bank_version"),
    )

    # Relationships
    bank: Mapped[Bank] = relationship(back_populates="parser_versions")
    documents: Mapped[list[Document]] = relationship(back_populates="parser_version")


# ─── Model Versions ─────────────────────────────────────────────────────────

class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Relationships
    documents: Mapped[list[Document]] = relationship(back_populates="model_version")


# ─── Documents ───────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    bank_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("banks.id"), nullable=True)
    parser_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parser_versions.id"), nullable=True
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    statement_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Google Drive Archival
    drive_file_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    drive_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    drive_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


    __table_args__ = (
        Index("ix_documents_status", "status"),
    )

    # Relationships
    bank: Mapped[Bank | None] = relationship(back_populates="documents")
    parser_version: Mapped[ParserVersion | None] = relationship(back_populates="documents")
    model_version: Mapped[ModelVersion | None] = relationship(back_populates="documents")
    pages: Mapped[list[DocumentPage]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number"
    )
    predicted_transactions: Mapped[list[PredictedTransaction]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="PredictedTransaction.sequence"
    )
    corrected_transactions: Mapped[list[CorrectedTransaction]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    training_samples: Mapped[list[TrainingSample]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


# ─── Document Pages ─────────────────────────────────────────────────────────

class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_page_doc_num"),
        Index("ix_docpages_document", "document_id"),
    )

    # Relationships
    document: Mapped[Document] = relationship(back_populates="pages")
    tokens: Mapped[list[TokenRecord]] = relationship(
        back_populates="page", cascade="all, delete-orphan", order_by="TokenRecord.sequence"
    )
    extracted_lines: Mapped[list[ExtractedLineRecord]] = relationship(
        back_populates="page", cascade="all, delete-orphan", order_by="ExtractedLineRecord.line_number"
    )


# ─── Tokens ──────────────────────────────────────────────────────────────────

class TokenRecord(Base):
    __tablename__ = "tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    x0: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y0: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_tokens_page", "page_id"),
    )

    # Relationships
    page: Mapped[DocumentPage] = relationship(back_populates="tokens")


# ─── Extracted Lines ─────────────────────────────────────────────────────────

class ExtractedLineRecord(Base):
    __tablename__ = "extracted_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_json: Mapped[dict | None] = mapped_column("tokens", JSON, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    y_center: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_lines_page", "page_id"),
    )

    # Relationships
    page: Mapped[DocumentPage] = relationship(back_populates="extracted_lines")


# ─── Predicted Transactions ─────────────────────────────────────────────────

class PredictedTransaction(Base):
    __tablename__ = "predicted_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    txn_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    reference_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    debit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    credit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    txn_type: Mapped[str] = mapped_column(String(20), default="unknown")
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    raw_text: Mapped[str] = mapped_column(Text, default="")

    confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_tokens: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_predicted_document", "document_id"),
        UniqueConstraint("document_id", "sequence", name="uq_predicted_doc_seq"),
    )

    # Relationships
    document: Mapped[Document] = relationship(back_populates="predicted_transactions")
    corrected: Mapped[CorrectedTransaction | None] = relationship(
        back_populates="predicted", uselist=False
    )
    training_samples: Mapped[list[TrainingSample]] = relationship(back_populates="predicted")


# ─── Corrected Transactions ─────────────────────────────────────────────────

class CorrectedTransaction(Base):
    __tablename__ = "corrected_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    predicted_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predicted_transactions.id"), nullable=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    txn_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    reference_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    debit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    credit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    txn_type: Mapped[str] = mapped_column(String(20), default="unknown")
    currency: Mapped[str] = mapped_column(String(10), default="INR")

    field_corrections: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correction_type: Mapped[str] = mapped_column(String(50), nullable=False, default="field_edit")
    corrected_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_corrected_document", "document_id"),
    )

    # Relationships
    predicted: Mapped[PredictedTransaction | None] = relationship(back_populates="corrected")
    document: Mapped[Document] = relationship(back_populates="corrected_transactions")
    training_samples: Mapped[list[TrainingSample]] = relationship(back_populates="corrected")


# ─── Training Samples ───────────────────────────────────────────────────────

class TrainingSample(Base):
    __tablename__ = "training_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    predicted_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predicted_transactions.id"), nullable=True
    )
    corrected_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corrected_transactions.id"), nullable=True
    )
    bank_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("banks.id"), nullable=True)
    parser_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parser_versions.id"), nullable=True
    )

    input_features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_training_document", "document_id"),
        Index("ix_training_bank", "bank_id"),
    )

    # Relationships
    document: Mapped[Document] = relationship(back_populates="training_samples")
    predicted: Mapped[PredictedTransaction | None] = relationship(back_populates="training_samples")
    corrected: Mapped[CorrectedTransaction | None] = relationship(back_populates="training_samples")
