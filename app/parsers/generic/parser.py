"""Generic Statement Parser.

Fallback parser that uses heuristic approaches when no bank-specific
parser is available. Uses adaptive column detection based on header analysis.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.core.types import (
    ExtractedLine, PageData, RawTransaction, FieldConfidence, Token,
)
from app.parsers.base import BaseParser, ParserConfig
from app.extraction.validator import TransactionValidator

logger = logging.getLogger(__name__)

# Months for date detection
MONTHS_SHORT = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}


class GenericParser(BaseParser):
    """Heuristic-based parser for unknown bank formats."""

    def __init__(self, config: ParserConfig):
        super().__init__(config)
        self._header_line_idx: Optional[int] = None
        self._column_boundaries: dict[str, tuple[float, float]] = {}

    def detect_table_region(self, pages: list[PageData]) -> list[ExtractedLine]:
        """Find transaction table by locating header row, then collecting data lines."""
        all_lines: list[ExtractedLine] = []
        in_table = False
        header_found = False

        for page in pages:
            for line in page.lines:
                if self._should_ignore_line(line):
                    continue

                # Look for header row
                if not header_found and self._is_header_line(line):
                    header_found = True
                    in_table = True
                    self._detect_column_boundaries(line)
                    self.logger.debug(f"Header found at page {page.page_number}, line {line.line_number}")
                    continue

                # Check for footer/end of table
                if in_table and self._is_footer_line(line):
                    in_table = False
                    continue

                if in_table:
                    all_lines.append(line)

        # If no header found, try treating all lines as potential data
        if not header_found:
            self.logger.warning("No header row found - attempting to parse all lines")
            for page in pages:
                for line in page.lines:
                    if not self._should_ignore_line(line) and self._looks_like_data_line(line):
                        all_lines.append(line)

        return all_lines

    def reconstruct_rows(
        self,
        table_lines: list[ExtractedLine],
        pages: list[PageData],
    ) -> list[list[ExtractedLine]]:
        """Group lines into transaction rows.

        Strategy:
        - A line starting with a date (or serial number + date) is a new transaction
        - Subsequent non-date lines are narration continuations
        """
        if not table_lines:
            return []

        rows: list[list[ExtractedLine]] = []
        current_row: list[ExtractedLine] = []

        for line in table_lines:
            if self._line_starts_new_transaction(line):
                if current_row:
                    rows.append(current_row)
                current_row = [line]
            else:
                # Continuation of previous row (multiline narration)
                if current_row:
                    current_row.append(line)
                else:
                    current_row = [line]

        if current_row:
            rows.append(current_row)

        return rows

    def _line_starts_new_transaction(self, line: ExtractedLine) -> bool:
        """Check if a line starts a new transaction using multiple heuristics."""
        if not line.tokens:
            return False

        tokens = line.tokens

        # Strategy 1: First token is a date (e.g., "01/03/2026")
        if self._is_date_like(tokens[0].text):
            return True

        # Strategy 2: First token is a serial number, second is a date
        if len(tokens) >= 2 and re.match(r"^\d{1,4}$", tokens[0].text.strip()):
            if self._is_date_like(tokens[1].text):
                return True

        # Strategy 3: Date spans multiple tokens: "02" "Mar" "2026"
        if len(tokens) >= 3:
            t0, t1, t2 = tokens[0].text.strip(), tokens[1].text.strip(), tokens[2].text.strip()
            if (re.match(r"^\d{1,2}$", t0) and
                t1.lower().rstrip(".,") in MONTHS_SHORT and
                re.match(r"^\d{2,4}$", t2)):
                return True

        # Strategy 4: First two tokens form a date: "02/03" "2026" or "02" "Mar"
        if len(tokens) >= 2:
            combined = tokens[0].text.strip() + " " + tokens[1].text.strip()
            if self._is_date_like(combined):
                return True

        return False

    def extract_fields(
        self,
        rows: list[list[ExtractedLine]],
        pages: list[PageData],
    ) -> list[RawTransaction]:
        """Extract transaction fields from grouped rows."""
        transactions: list[RawTransaction] = []

        for row_lines in rows:
            txn = self._extract_single_row(row_lines)
            if txn:
                transactions.append(txn)

        return transactions

    def _extract_single_row(self, row_lines: list[ExtractedLine]) -> Optional[RawTransaction]:
        """Extract fields from a single transaction row (1+ lines)."""
        if not row_lines:
            return None

        all_tokens: list[Token] = []
        for line in row_lines:
            all_tokens.extend(line.tokens)

        raw_text = " | ".join(line.text for line in row_lines)
        page_start = row_lines[0].page
        page_end = row_lines[-1].page

        txn = RawTransaction(
            raw_text=raw_text,
            source_tokens=[t.to_dict() for t in all_tokens[:50]],  # Cap token storage
            page_start=page_start,
            page_end=page_end,
        )

        # If we have column boundaries from header detection, use coordinate-based extraction
        if self._column_boundaries:
            txn = self._extract_by_coordinates(txn, all_tokens)
        else:
            txn = self._extract_by_heuristics(txn, row_lines, all_tokens)

        return txn

    def _extract_by_coordinates(
        self, txn: RawTransaction, tokens: list[Token]
    ) -> RawTransaction:
        """Extract fields using detected column x-boundaries."""
        for col_name, (x_start, x_end) in self._column_boundaries.items():
            col_tokens = self._tokens_in_range(tokens, x_start, x_end)
            col_text = " ".join(t.text for t in col_tokens).strip()

            if not col_text:
                continue

            col_lower = col_name.lower()
            if "date" in col_lower and not txn.txn_date:
                txn.txn_date = col_text
            elif "value" in col_lower and "date" in col_lower:
                txn.value_date = col_text
            elif any(k in col_lower for k in ["narration", "description", "particular", "remark"]):
                txn.description = col_text
            elif any(k in col_lower for k in ["ref", "chq", "cheque"]):
                txn.reference_no = col_text
            elif "debit" in col_lower or "withdrawal" in col_lower:
                txn.debit = TransactionValidator.parse_amount(col_text)
            elif "credit" in col_lower or "deposit" in col_lower:
                txn.credit = TransactionValidator.parse_amount(col_text)
            elif "balance" in col_lower:
                txn.balance = TransactionValidator.parse_amount(col_text)

        return txn

    def _extract_by_heuristics(
        self,
        txn: RawTransaction,
        row_lines: list[ExtractedLine],
        all_tokens: list[Token],
    ) -> RawTransaction:
        """Fallback: extract fields using text pattern matching."""
        desc_parts: list[str] = []
        amounts_found: list[float] = []
        i = 0

        while i < len(all_tokens):
            text = all_tokens[i].text.strip()

            # Try multi-token date: "02 Mar 2026"
            if (i + 2 < len(all_tokens) and
                re.match(r"^\d{1,2}$", text) and
                all_tokens[i+1].text.strip().lower().rstrip(".,") in MONTHS_SHORT):
                date_str = f"{text} {all_tokens[i+1].text.strip()} {all_tokens[i+2].text.strip()}"
                if not txn.txn_date:
                    txn.txn_date = date_str
                elif not txn.value_date:
                    txn.value_date = date_str
                i += 3
                continue

            # Single-token date
            if self._is_date_like(text):
                if not txn.txn_date:
                    txn.txn_date = text
                elif not txn.value_date:
                    txn.value_date = text
                i += 1
                continue

            # Amounts
            if self._is_amount_like(text):
                parsed = TransactionValidator.parse_amount(text)
                if parsed is not None:
                    amounts_found.append(parsed)
                i += 1
                continue

            desc_parts.append(text)
            i += 1

        txn.description = " ".join(desc_parts).strip()

        # Assign amounts: typically [debit/credit, balance] or [amount, balance]
        if len(amounts_found) >= 2:
            txn.balance = amounts_found[-1]
            amount = amounts_found[-2]
            txn.debit = amount  # Can't determine debit vs credit without context
        elif len(amounts_found) == 1:
            txn.balance = amounts_found[0]

        return txn

    # --- Header/Table Detection ---

    def _is_header_line(self, line: ExtractedLine) -> bool:
        """Check if a line is the transaction table header."""
        text_lower = line.text.lower()
        keywords = self.config.header_keywords or [
            "date", "narration", "debit", "credit", "balance",
        ]

        match_count = sum(1 for kw in keywords if kw.lower() in text_lower)
        return match_count >= 3

    def _is_footer_line(self, line: ExtractedLine) -> bool:
        """Check if a line indicates end of transaction table."""
        text = line.text.strip()
        for keyword in self.config.footer_keywords:
            if re.search(keyword, text, re.IGNORECASE):
                return True
        return False

    def _looks_like_data_line(self, line: ExtractedLine) -> bool:
        """Check if a line looks like it could contain transaction data."""
        if not line.tokens:
            return False
        has_date = any(self._is_date_like(t.text) for t in line.tokens)
        has_amount = any(self._is_amount_like(t.text) for t in line.tokens)
        # Also check multi-token dates
        if not has_date and len(line.tokens) >= 3:
            for j in range(len(line.tokens) - 2):
                t0 = line.tokens[j].text.strip()
                t1 = line.tokens[j+1].text.strip().lower().rstrip(".,")
                if re.match(r"^\d{1,2}$", t0) and t1 in MONTHS_SHORT:
                    has_date = True
                    break
        return has_date and has_amount

    def _detect_column_boundaries(self, header_line: ExtractedLine) -> None:
        """Detect column x-boundaries from the header line tokens."""
        self._column_boundaries = {}
        for token in header_line.tokens:
            col_name = token.text.strip()
            if col_name:
                self._column_boundaries[col_name] = (token.x0, token.x1)

        # Expand boundaries: each column extends from its start to the next column's start
        sorted_cols = sorted(self._column_boundaries.items(), key=lambda x: x[1][0])
        expanded: dict[str, tuple[float, float]] = {}

        for i, (name, (x_start, x_end)) in enumerate(sorted_cols):
            if i + 1 < len(sorted_cols):
                next_start = sorted_cols[i + 1][1][0]
                expanded[name] = (x_start, next_start - 1)
            else:
                expanded[name] = (x_start, 9999.0)

        self._column_boundaries = expanded
        self.logger.debug(f"Detected columns: {list(self._column_boundaries.keys())}")
