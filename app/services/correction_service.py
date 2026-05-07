"""Correction Service — handles transaction corrections and training data generation."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types import DocumentStatus
from app.db.models import CorrectedTransaction, TrainingSample, Document
from app.extraction.validator import TransactionValidator
from app.repositories.document_repo import DocumentRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.training_repo import TrainingRepository
from app.schemas.transaction import BulkCorrectionRequest, TransactionCorrectionRequest

logger = logging.getLogger(__name__)


class CorrectionService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.txn_repo = TransactionRepository(session)
        self.training_repo = TrainingRepository(session)

    async def submit_corrections(self, request: BulkCorrectionRequest) -> list[CorrectedTransaction]:
        """Process bulk corrections for a document and generate training data."""

        doc = await self.doc_repo.get_by_id(request.document_id)
        if not doc:
            raise ValueError(f"Document {request.document_id} not found")

        # Clear previous corrections for this document
        await self.txn_repo.delete_corrected_by_document(request.document_id)

        corrected_records: list[CorrectedTransaction] = []
        training_samples: list[TrainingSample] = []

        for txn_correction in request.transactions:
            corrected = self._build_corrected_record(doc, txn_correction)
            corrected_records.append(corrected)

            # Generate training sample from the prediction → correction pair
            sample = await self._build_training_sample(doc, txn_correction, corrected)
            if sample:
                training_samples.append(sample)

        if corrected_records:
            await self.txn_repo.save_corrected(corrected_records)

        if training_samples:
            await self.training_repo.save_samples(training_samples)

        # Update document status
        doc.status = DocumentStatus.CONFIRMED.value
        await self.session.flush()

        logger.info(
            f"Corrections saved: {len(corrected_records)} transactions, "
            f"{len(training_samples)} training samples for doc {doc.id}"
        )

        return corrected_records

    def _build_corrected_record(
        self, doc: Document, correction: TransactionCorrectionRequest
    ) -> CorrectedTransaction:
        """Build a CorrectedTransaction from the correction request."""
        parsed_date = TransactionValidator.parse_date(correction.txn_date) if correction.txn_date else None
        parsed_vdate = TransactionValidator.parse_date(correction.value_date) if correction.value_date else None

        field_corrections = {
            c.field_name: {"old": c.old_value, "new": c.new_value}
            for c in correction.corrections
        }

        return CorrectedTransaction(
            predicted_id=correction.predicted_id,
            document_id=doc.id,
            sequence=correction.sequence,
            txn_date=parsed_date,
            value_date=parsed_vdate,
            description=correction.description,
            reference_no=correction.reference_no,
            debit=correction.debit,
            credit=correction.credit,
            balance=correction.balance,
            txn_type=correction.txn_type,
            currency=correction.currency,
            field_corrections=field_corrections,
            correction_type=correction.correction_type,
        )

    async def _build_training_sample(
        self,
        doc: Document,
        correction: TransactionCorrectionRequest,
        corrected: CorrectedTransaction,
    ) -> Optional[TrainingSample]:
        """Build a training sample from a correction pair."""
        predicted = None
        if correction.predicted_id:
            predicted = await self.txn_repo.get_predicted_by_id(correction.predicted_id)

        input_features = {}
        expected_output = {}

        if predicted:
            input_features = {
                "raw_text": predicted.raw_text,
                "source_tokens": predicted.source_tokens,
                "predicted_date": str(predicted.txn_date) if predicted.txn_date else None,
                "predicted_description": predicted.description,
                "predicted_debit": float(predicted.debit) if predicted.debit else None,
                "predicted_credit": float(predicted.credit) if predicted.credit else None,
                "predicted_balance": float(predicted.balance) if predicted.balance else None,
            }

        expected_output = {
            "txn_date": str(corrected.txn_date) if corrected.txn_date else None,
            "description": corrected.description,
            "debit": float(corrected.debit) if corrected.debit else None,
            "credit": float(corrected.credit) if corrected.credit else None,
            "balance": float(corrected.balance) if corrected.balance else None,
            "txn_type": corrected.txn_type,
        }

        return TrainingSample(
            document_id=doc.id,
            predicted_id=correction.predicted_id,
            corrected_id=corrected.id,
            bank_id=doc.bank_id,
            parser_version_id=doc.parser_version_id,
            input_features=input_features,
            expected_output=expected_output,
            token_context=predicted.source_tokens if predicted else None,
        )
