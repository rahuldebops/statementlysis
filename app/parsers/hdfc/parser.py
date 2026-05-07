"""HDFC Bank Statement Parser.

Handles HDFC savings/current account statements with standard column layout:
Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.core.types import (
    ExtractedLine, PageData, RawTransaction, Token,
)
from app.parsers.base import BaseParser, ParserConfig, ColumnConfig
from app.extraction.validator import TransactionValidator

logger = logging.getLogger(__name__)


class HDFCParser(BaseParser):
    """Parser for HDFC Bank statements."""

    def __init__(self, config: ParserConfig):
        super().__init__(config)
        self._col_map = {col.name: col for col in config.columns}

    def detect_table_region(self, pages: list[PageData]) -> list[ExtractedLine]:
        """Find transaction lines in HDFC statement.

        HDFC statements typically have:
        - Account info header at the top
        - Column header row
        - Transaction data
        - Statement summary at bottom
        """
        all_data_lines: list[ExtractedLine] = []
        in_table = False

        for page in pages:
            for line in page.lines:
                if self._should_ignore_line(line):
                    continue

                text = line.text.strip()

                # Detect header row
                if not in_table and self._is_hdfc_header(text):
                    in_table = True
                    # Recalibrate column boundaries from this actual header
                    self._calibrate_columns(line)
                    continue

                # Detect end of table
                if in_table and self._is_hdfc_footer(text):
                    in_table = False
                    continue

                if in_table and text:
                    all_data_lines.append(line)

        return all_data_lines

    def reconstruct_rows(
        self,
        table_lines: list[ExtractedLine],
        pages: list[PageData],
    ) -> list[list[ExtractedLine]]:
        """Group lines into transaction rows.

        HDFC narrations can span multiple lines. A new transaction starts
        when a line begins with a date in the Date column region.
        """
        if not table_lines:
            return []

        rows: list[list[ExtractedLine]] = []
        current_row: list[ExtractedLine] = []

        date_col = self._col_map.get("date")

        for line in table_lines:
            is_new_txn = False

            if date_col:
                # Check if the first token falls in the date column
                date_tokens = self._tokens_in_column(line.tokens, date_col, tolerance=10)
                if date_tokens and self._is_date_like(date_tokens[0].text):
                    is_new_txn = True
            else:
                # Fallback: check if the first token looks like a date
                if line.tokens and self._is_date_like(line.tokens[0].text):
                    is_new_txn = True

            if is_new_txn:
                if current_row:
                    rows.append(current_row)
                current_row = [line]
            else:
                # Continuation line (multiline narration)
                if current_row:
                    current_row.append(line)
                else:
                    current_row = [line]

        if current_row:
            rows.append(current_row)

        return rows

    def extract_fields(
        self,
        rows: list[list[ExtractedLine]],
        pages: list[PageData],
    ) -> list[RawTransaction]:
        """Extract structured fields from HDFC transaction rows."""
        transactions: list[RawTransaction] = []

        for row_lines in rows:
            txn = self._extract_hdfc_row(row_lines)
            if txn:
                transactions.append(txn)

        return transactions

    def _extract_hdfc_row(self, row_lines: list[ExtractedLine]) -> Optional[RawTransaction]:
        """Extract a single HDFC transaction from its constituent lines."""
        if not row_lines:
            return None

        all_tokens: list[Token] = []
        for line in row_lines:
            all_tokens.extend(line.tokens)

        raw_text = " | ".join(line.text for line in row_lines)

        txn = RawTransaction(
            raw_text=raw_text,
            source_tokens=[t.to_dict() for t in all_tokens],
            page_start=row_lines[0].page,
            page_end=row_lines[-1].page,
        )

        # Extract using column coordinates
        # Date
        if "date" in self._col_map:
            date_tokens = self._tokens_in_column(all_tokens, self._col_map["date"], tolerance=10)
            if date_tokens:
                txn.txn_date = " ".join(t.text for t in date_tokens).strip()

        # Narration (description) — may span multiple lines
        if "narration" in self._col_map:
            narr_tokens = self._tokens_in_column(all_tokens, self._col_map["narration"], tolerance=10)
            txn.description = " ".join(t.text for t in narr_tokens).strip()

        # Chq/Ref No
        if "chq_ref" in self._col_map:
            ref_tokens = self._tokens_in_column(all_tokens, self._col_map["chq_ref"], tolerance=10)
            if ref_tokens:
                txn.reference_no = " ".join(t.text for t in ref_tokens).strip()

        # Value Date
        if "value_date" in self._col_map:
            vd_tokens = self._tokens_in_column(all_tokens, self._col_map["value_date"], tolerance=10)
            if vd_tokens:
                txn.value_date = " ".join(t.text for t in vd_tokens).strip()

        # Withdrawal (Debit)
        if "withdrawal" in self._col_map:
            wd_tokens = self._tokens_in_column(all_tokens, self._col_map["withdrawal"], tolerance=10)
            if wd_tokens:
                wd_text = " ".join(t.text for t in wd_tokens).strip()
                txn.debit = TransactionValidator.parse_amount(wd_text)

        # Deposit (Credit)
        if "deposit" in self._col_map:
            dep_tokens = self._tokens_in_column(all_tokens, self._col_map["deposit"], tolerance=10)
            if dep_tokens:
                dep_text = " ".join(t.text for t in dep_tokens).strip()
                txn.credit = TransactionValidator.parse_amount(dep_text)

        # Closing Balance
        if "balance" in self._col_map:
            bal_tokens = self._tokens_in_column(all_tokens, self._col_map["balance"], tolerance=10)
            if bal_tokens:
                bal_text = " ".join(t.text for t in bal_tokens).strip()
                txn.balance = TransactionValidator.parse_amount(bal_text)

        return txn

    # ─── HDFC-specific helpers ──────────────────────────────────────────

    def _is_hdfc_header(self, text: str) -> bool:
        """Check if this line is the HDFC transaction table header."""
        text_lower = text.lower()
        required = ["date", "narration"]
        optional = ["withdrawal", "deposit", "balance", "chq", "ref", "value"]

        has_required = all(kw in text_lower for kw in required)
        optional_count = sum(1 for kw in optional if kw in text_lower)

        return has_required and optional_count >= 2

    def _is_hdfc_footer(self, text: str) -> bool:
        """Check if this line marks the end of the transaction table."""
        footer_patterns = [
            r"Statement\s+Summary",
            r"OPENING\s+BALANCE",
            r"CLOSING\s+BALANCE",
            r"^\s*\*{3,}",
            r"This\s+is\s+a\s+computer\s+generated",
        ]
        for pattern in footer_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _calibrate_columns(self, header_line: ExtractedLine) -> None:
        """Recalibrate column boundaries from the actual header line tokens.

        This handles PDF layout variations where columns shift slightly.
        """
        for token in header_line.tokens:
            text = token.text.strip().lower()

            # Map header text to column names
            col_mapping = {
                "date": "date",
                "narration": "narration",
                "chq": "chq_ref",
                "ref": "chq_ref",
                "value": "value_date",
                "withdrawal": "withdrawal",
                "deposit": "deposit",
                "closing": "balance",
                "balance": "balance",
            }

            for keyword, col_name in col_mapping.items():
                if keyword in text and col_name in self._col_map:
                    col = self._col_map[col_name]
                    # Update the column's x_start based on actual header position
                    self._col_map[col_name] = ColumnConfig(
                        name=col.name,
                        x_start=token.x0,
                        x_end=col.x_end,  # Keep original end or recalculate
                        required=col.required,
                        aliases=col.aliases,
                    )

        self.logger.debug(f"Calibrated columns: {[c.name for c in self._col_map.values()]}")
