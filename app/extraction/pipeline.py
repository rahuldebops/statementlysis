"""Extraction Pipeline Orchestrator.

Coordinates the full extraction flow:
PDF → tokens → lines → bank detection → parser selection → transactions → validation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.core.types import PageData, RawTransaction, BankDetectionResult
from app.extraction.pdf_engine import PDFEngine
from app.extraction.line_builder import LineBuilder
from app.extraction.bank_detector import BankDetector
from app.extraction.validator import TransactionValidator
from app.parsers.registry import ParserRegistry

logger = logging.getLogger(__name__)


class ExtractionPipeline:
    """Orchestrates the full extraction pipeline."""

    def __init__(self):
        self.pdf_engine = PDFEngine()
        self.line_builder = LineBuilder()
        self.bank_detector = BankDetector()
        self.validator = TransactionValidator()

    def run(
        self,
        pdf_path: str | Path,
        password: Optional[str] = None,
        force_bank: Optional[str] = None,
    ) -> "ExtractionResult":
        """Execute the full extraction pipeline.

        Args:
            pdf_path: Path to the PDF file
            password: Optional PDF password
            force_bank: Force a specific bank parser (skip detection)
        """
        logger.info(f"Starting extraction pipeline for: {pdf_path}")

        # Step 1: Extract tokens from PDF
        pages = self.pdf_engine.extract(pdf_path, password=password)
        logger.info(f"Step 1 complete: {len(pages)} pages, "
                    f"{sum(len(p.tokens) for p in pages)} tokens")

        # Step 2: Build lines from tokens
        pages = self.line_builder.build_all_pages(pages)
        total_lines = sum(len(p.lines) for p in pages)
        logger.info(f"Step 2 complete: {total_lines} lines reconstructed")

        # Step 3: Detect bank
        if force_bank:
            bank_result = BankDetectionResult(
                bank_id=force_bank,
                bank_name=force_bank.upper(),
                confidence=1.0,
            )
        else:
            bank_result = self.bank_detector.detect(pages)

        logger.info(f"Step 3 complete: bank={bank_result.bank_id}, "
                    f"confidence={bank_result.confidence:.2f}")

        # Step 4: Select and run parser
        parser = ParserRegistry.get_or_fallback(bank_result.bank_id)
        transactions = parser.parse(pages)
        logger.info(f"Step 4 complete: {len(transactions)} transactions extracted "
                    f"using {parser.__class__.__name__}")

        # Step 5: Validate and score
        transactions = self.validator.validate_transactions(transactions)
        logger.info(f"Step 5 complete: validation done")

        return ExtractionResult(
            pages=pages,
            bank_result=bank_result,
            transactions=transactions,
            parser_name=parser.__class__.__name__,
            parser_version=parser.version,
        )


class ExtractionResult:
    """Holds the complete result of an extraction pipeline run."""

    def __init__(
        self,
        pages: list[PageData],
        bank_result: BankDetectionResult,
        transactions: list[RawTransaction],
        parser_name: str,
        parser_version: str,
    ):
        self.pages = pages
        self.bank_result = bank_result
        self.transactions = transactions
        self.parser_name = parser_name
        self.parser_version = parser_version

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def total_tokens(self) -> int:
        return sum(len(p.tokens) for p in self.pages)

    @property
    def total_lines(self) -> int:
        return sum(len(p.lines) for p in self.pages)

    @property
    def transaction_count(self) -> int:
        return len(self.transactions)
