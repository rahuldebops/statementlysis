"""Abstract Base Parser.

Defines the contract that all bank-specific parsers must implement.
Each parser is responsible for:
1. Detecting the transaction table region
2. Reconstructing transaction rows from lines
3. Extracting individual fields from rows
4. Validating and assigning confidence scores
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.core.types import (
    ExtractedLine, PageData, RawTransaction, FieldConfidence, Token,
)

logger = logging.getLogger(__name__)


@dataclass
class ColumnConfig:
    """Configuration for a single column in the statement table."""
    name: str
    x_start: float
    x_end: float
    required: bool = False
    aliases: list[str] = field(default_factory=list)


@dataclass
class ParserConfig:
    """Configuration loaded from a parser's config.json."""
    bank_id: str
    version: str
    headers: list[str] = field(default_factory=list)
    date_patterns: list[str] = field(default_factory=list)
    amount_patterns: list[str] = field(default_factory=list)
    ignore_patterns: list[str] = field(default_factory=list)
    columns: list[ColumnConfig] = field(default_factory=list)
    header_keywords: list[str] = field(default_factory=list)
    footer_keywords: list[str] = field(default_factory=list)
    multiline_narration: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, config_path: Path) -> "ParserConfig":
        """Load parser configuration from a JSON file."""
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        columns = [
            ColumnConfig(**col) for col in data.get("columns", [])
        ]

        return cls(
            bank_id=data.get("bank_id", "unknown"),
            version=data.get("version", "1.0.0"),
            headers=data.get("headers", []),
            date_patterns=data.get("date_patterns", []),
            amount_patterns=data.get("amount_patterns", []),
            ignore_patterns=data.get("ignore_patterns", []),
            columns=columns,
            header_keywords=data.get("header_keywords", []),
            footer_keywords=data.get("footer_keywords", []),
            multiline_narration=data.get("multiline_narration", True),
            extra=data.get("extra", {}),
        )


class BaseParser(ABC):
    """Abstract base class for bank statement parsers.

    Subclasses must implement the extraction pipeline methods.
    The parser framework calls these in order:
        detect_table_region → reconstruct_rows → extract_fields → validate
    """

    def __init__(self, config: ParserConfig):
        self.config = config
        self.logger = logging.getLogger(f"parser.{config.bank_id}")

    @property
    def bank_id(self) -> str:
        return self.config.bank_id

    @property
    def version(self) -> str:
        return self.config.version

    def parse(self, pages: list[PageData]) -> list[RawTransaction]:
        """Full parse pipeline: table detection → row reconstruction → field extraction.

        This is the main entry point called by the extraction service.
        """
        self.logger.info(
            f"Parsing {len(pages)} pages with {self.bank_id} parser v{self.version}"
        )

        # Step 1: Find the transaction table boundaries
        table_lines = self.detect_table_region(pages)
        self.logger.debug(f"Table region: {len(table_lines)} lines identified")

        # Step 2: Group lines into transaction rows (handling multiline narrations)
        raw_rows = self.reconstruct_rows(table_lines, pages)
        self.logger.debug(f"Reconstructed {len(raw_rows)} transaction rows")

        # Step 3: Extract structured fields from each row
        transactions = self.extract_fields(raw_rows, pages)
        self.logger.info(f"Extracted {len(transactions)} transactions")

        # Step 4: Assign sequence numbers
        for i, txn in enumerate(transactions):
            txn.sequence = i + 1

        return transactions

    @abstractmethod
    def detect_table_region(self, pages: list[PageData]) -> list[ExtractedLine]:
        """Identify lines that belong to the transaction table.

        Must filter out headers, footers, account info sections, etc.
        Returns only the lines that contain transaction data.
        """
        ...

    @abstractmethod
    def reconstruct_rows(
        self,
        table_lines: list[ExtractedLine],
        pages: list[PageData],
    ) -> list[list[ExtractedLine]]:
        """Group table lines into logical transaction rows.

        Must handle:
        - Single-line transactions
        - Multi-line narrations/descriptions
        - Wrapped text across lines
        - Page boundaries

        Returns a list of groups, where each group is 1+ lines forming one transaction.
        """
        ...

    @abstractmethod
    def extract_fields(
        self,
        rows: list[list[ExtractedLine]],
        pages: list[PageData],
    ) -> list[RawTransaction]:
        """Extract structured fields from grouped row lines.

        Must extract:
        - txn_date, value_date
        - description
        - reference_no
        - debit, credit
        - balance
        - raw_text

        Uses coordinate-based column detection primarily.
        """
        ...

    # ─── Utility methods for subclasses ───────────────────────────────────

    def _tokens_in_column(
        self, tokens: list[Token], col: ColumnConfig, tolerance: float = 5.0
    ) -> list[Token]:
        """Get tokens that fall within a column's x-range."""
        return [
            t for t in tokens
            if t.x0 >= (col.x_start - tolerance) and t.x1 <= (col.x_end + tolerance)
        ]

    def _tokens_in_range(
        self, tokens: list[Token], x_start: float, x_end: float, tolerance: float = 5.0
    ) -> list[Token]:
        """Get tokens whose center falls within an x-range."""
        return [
            t for t in tokens
            if (t.x0 + t.x1) / 2 >= (x_start - tolerance)
            and (t.x0 + t.x1) / 2 <= (x_end + tolerance)
        ]

    def _is_date_like(self, text: str) -> bool:
        """Check if text looks like a date."""
        import re
        date_patterns = self.config.date_patterns or [
            r"\d{2}[/\-]\d{2}[/\-]\d{2,4}",
            r"\d{2}\s+\w{3}\s+\d{2,4}",
        ]
        # Also add common Indian patterns always
        extra_patterns = [
            r"\d{2}[/\-]\d{2}[/\-]\d{2,4}",
            r"\d{2}\s+\w{3}\s+\d{2,4}",
            r"\d{2}\s+\w{3},?\s+\d{2,4}",
            r"\d{2}\s+\w{3}\s+'\d{2}",
        ]
        all_patterns = list(set(date_patterns + extra_patterns))
        for pattern in all_patterns:
            if re.match(pattern, text.strip()):
                return True
        return False

    def _is_amount_like(self, text: str) -> bool:
        """Check if text looks like a currency amount."""
        import re
        cleaned = text.strip().replace(",", "").replace(" ", "")
        return bool(re.match(r"^\d+\.?\d*$", cleaned))

    def _should_ignore_line(self, line: ExtractedLine) -> bool:
        """Check if a line matches any ignore pattern."""
        import re
        text = line.text
        for pattern in self.config.ignore_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
