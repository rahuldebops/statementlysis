"""SBI (State Bank of India) Statement Parser.

Handles SBI savings/current account statements.
Real format: # | Date | Description | Chq/Ref. No. | Withdrawal (Dr.) | Deposit (Cr.) | Balance
Dates are multi-token: "02 Mar 2026"
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.core.types import ExtractedLine, PageData, RawTransaction, Token
from app.parsers.base import BaseParser, ParserConfig, ColumnConfig
from app.extraction.validator import TransactionValidator

logger = logging.getLogger(__name__)

MONTHS_SHORT = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}


class SBIParser(BaseParser):
    """Parser for SBI bank statements."""

    def __init__(self, config: ParserConfig):
        super().__init__(config)
        self._col_map = {col.name: col for col in config.columns}
        self._header_count = 0

    def detect_table_region(self, pages: list[PageData]) -> list[ExtractedLine]:
        all_data_lines: list[ExtractedLine] = []
        in_table = False

        for page in pages:
            for line in page.lines:
                if self._should_ignore_line(line):
                    continue

                text = line.text.strip()

                if self._is_sbi_header(text):
                    if self._header_count == 0:
                        self._calibrate_columns(line)
                    self._header_count += 1
                    in_table = True
                    continue

                if in_table and self._is_sbi_footer(text):
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
        if not table_lines:
            return []

        rows: list[list[ExtractedLine]] = []
        current_row: list[ExtractedLine] = []

        for line in table_lines:
            is_new_txn = self._line_starts_new_sbi_txn(line)

            if is_new_txn:
                if current_row:
                    rows.append(current_row)
                current_row = [line]
            else:
                if current_row:
                    current_row.append(line)
                else:
                    current_row = [line]

        if current_row:
            rows.append(current_row)

        return rows

    def _line_starts_new_sbi_txn(self, line: ExtractedLine) -> bool:
        """Detect if this line starts a new transaction.
        
        SBI lines start with a serial number followed by a date.
        Pattern: "1" "02" "Mar" "2026" ... or just "02" "Mar" "2026" ...
        """
        if not line.tokens:
            return False

        tokens = line.tokens
        idx = 0

        # Skip serial number if present (1-4 digits at far left)
        serial_col = self._col_map.get("serial")
        if serial_col and tokens[0].x0 < serial_col.x_end + 5:
            if re.match(r"^\d{1,4}$", tokens[0].text.strip()):
                idx = 1

        # Now check for a date in the date column region
        date_col = self._col_map.get("txn_date")
        
        # Check multi-token date: "02" "Mar" "2026"
        if idx + 2 < len(tokens):
            t0, t1, t2 = tokens[idx], tokens[idx+1], tokens[idx+2]
            if (re.match(r"^\d{1,2}$", t0.text.strip()) and
                t1.text.strip().lower().rstrip(".,") in MONTHS_SHORT and
                re.match(r"^\d{2,4}$", t2.text.strip())):
                # If we have a date column, also verify the x-position
                if date_col:
                    if t0.x0 >= date_col.x_start - 10:
                        return True
                else:
                    return True

        # Check single-token date
        if idx < len(tokens):
            if self._is_date_like(tokens[idx].text):
                return True

        return False

    def extract_fields(
        self,
        rows: list[list[ExtractedLine]],
        pages: list[PageData],
    ) -> list[RawTransaction]:
        transactions: list[RawTransaction] = []

        for row_lines in rows:
            txn = self._extract_sbi_row(row_lines)
            if txn:
                transactions.append(txn)

        return transactions

    def _extract_sbi_row(self, row_lines: list[ExtractedLine]) -> Optional[RawTransaction]:
        if not row_lines:
            return None

        all_tokens: list[Token] = []
        for line in row_lines:
            all_tokens.extend(line.tokens)

        raw_text = " | ".join(line.text for line in row_lines)

        txn = RawTransaction(
            raw_text=raw_text[:5000],
            source_tokens=[t.to_dict() for t in all_tokens[:50]],
            page_start=row_lines[0].page,
            page_end=row_lines[-1].page,
        )

        # Date (may be multi-token)
        if "txn_date" in self._col_map:
            tokens = self._tokens_in_column(all_tokens, self._col_map["txn_date"], tolerance=10)
            if tokens:
                txn.txn_date = " ".join(t.text for t in tokens).strip()

        # Description
        if "description" in self._col_map:
            tokens = self._tokens_in_column(all_tokens, self._col_map["description"], tolerance=10)
            txn.description = " ".join(t.text for t in tokens).strip()

        # Reference
        if "ref_no" in self._col_map:
            tokens = self._tokens_in_column(all_tokens, self._col_map["ref_no"], tolerance=10)
            if tokens:
                txn.reference_no = " ".join(t.text for t in tokens).strip()

        # Debit (Withdrawal)
        if "debit" in self._col_map:
            tokens = self._tokens_in_column(all_tokens, self._col_map["debit"], tolerance=10)
            if tokens:
                txn.debit = TransactionValidator.parse_amount(
                    " ".join(t.text for t in tokens).strip()
                )

        # Credit (Deposit)
        if "credit" in self._col_map:
            tokens = self._tokens_in_column(all_tokens, self._col_map["credit"], tolerance=10)
            if tokens:
                txn.credit = TransactionValidator.parse_amount(
                    " ".join(t.text for t in tokens).strip()
                )

        # Balance
        if "balance" in self._col_map:
            tokens = self._tokens_in_column(all_tokens, self._col_map["balance"], tolerance=10)
            if tokens:
                txn.balance = TransactionValidator.parse_amount(
                    " ".join(t.text for t in tokens).strip()
                )

        return txn

    def _is_sbi_header(self, text: str) -> bool:
        text_lower = text.lower()
        # SBI uses "Withdrawal (Dr.)" and "Deposit (Cr.)" instead of debit/credit
        required = ["date"]
        optional = ["description", "withdrawal", "deposit", "balance", "chq", "ref", "debit", "credit"]
        has_required = all(kw in text_lower for kw in required)
        optional_count = sum(1 for kw in optional if kw in text_lower)
        return has_required and optional_count >= 2

    def _is_sbi_footer(self, text: str) -> bool:
        for pattern in [r"Statement\s+Generated", r"Closing\s+Balance", r"Account\s+Summary", r"^\*{3,}"]:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _calibrate_columns(self, header_line: ExtractedLine) -> None:
        """Calibrate column boundaries from the actual header token positions."""
        # Map header keywords to column names
        keyword_map = {
            "#": "serial",
            "date": "txn_date",
            "description": "description",
            "chq": "ref_no", "chq/ref.": "ref_no", "ref.": "ref_no",
            "withdrawal": "debit", "debit": "debit",
            "deposit": "credit", "credit": "credit",
            "balance": "balance",
        }

        calibrated = {}
        for token in header_line.tokens:
            text_lower = token.text.strip().lower().rstrip(".,")
            for keyword, col_name in keyword_map.items():
                if keyword in text_lower and col_name not in calibrated:
                    calibrated[col_name] = token.x0
                    break

        # Rebuild column boundaries from calibrated x-positions
        sorted_cals = sorted(calibrated.items(), key=lambda x: x[1])
        for i, (col_name, x_start) in enumerate(sorted_cals):
            if col_name in self._col_map:
                x_end = sorted_cals[i+1][1] - 2 if i + 1 < len(sorted_cals) else 700
                self._col_map[col_name] = ColumnConfig(
                    name=col_name, x_start=x_start, x_end=x_end,
                    required=self._col_map[col_name].required,
                    aliases=self._col_map[col_name].aliases,
                )

        self.logger.info(f"Calibrated SBI columns: {[(n, c.x_start, c.x_end) for n, c in self._col_map.items()]}")
