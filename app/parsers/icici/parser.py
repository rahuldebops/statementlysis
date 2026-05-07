"""ICICI Bank Statement Parser.

Handles ICICI savings/current account statements.
Layout: S.No | Value Date | Txn Date | Cheque No | Remarks | Withdrawal | Deposit | Balance
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.core.types import ExtractedLine, PageData, RawTransaction, Token
from app.parsers.base import BaseParser, ParserConfig, ColumnConfig
from app.extraction.validator import TransactionValidator

logger = logging.getLogger(__name__)


class ICICIParser(BaseParser):

    def __init__(self, config: ParserConfig):
        super().__init__(config)
        self._col_map = {col.name: col for col in config.columns}

    def detect_table_region(self, pages: list[PageData]) -> list[ExtractedLine]:
        all_data_lines: list[ExtractedLine] = []
        in_table = False

        for page in pages:
            for line in page.lines:
                if self._should_ignore_line(line):
                    continue
                text = line.text.strip()
                if not in_table and self._is_icici_header(text):
                    in_table = True
                    self._calibrate_columns(line)
                    continue
                if in_table and self._is_icici_footer(text):
                    in_table = False
                    continue
                if in_table and text:
                    all_data_lines.append(line)

        return all_data_lines

    def reconstruct_rows(self, table_lines: list[ExtractedLine], pages: list[PageData]) -> list[list[ExtractedLine]]:
        if not table_lines:
            return []
        rows: list[list[ExtractedLine]] = []
        current_row: list[ExtractedLine] = []
        date_col = self._col_map.get("txn_date")

        for line in table_lines:
            is_new = False
            if date_col:
                dt = self._tokens_in_column(line.tokens, date_col, tolerance=10)
                if dt and self._is_date_like(dt[0].text):
                    is_new = True
            else:
                if line.tokens and self._is_date_like(line.tokens[0].text):
                    is_new = True
            if is_new:
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

    def extract_fields(self, rows: list[list[ExtractedLine]], pages: list[PageData]) -> list[RawTransaction]:
        return [txn for row in rows if (txn := self._extract_row(row))]

    def _extract_row(self, row_lines: list[ExtractedLine]) -> Optional[RawTransaction]:
        if not row_lines:
            return None
        all_tokens: list[Token] = []
        for line in row_lines:
            all_tokens.extend(line.tokens)
        raw_text = " | ".join(l.text for l in row_lines)
        txn = RawTransaction(raw_text=raw_text, source_tokens=[t.to_dict() for t in all_tokens],
                             page_start=row_lines[0].page, page_end=row_lines[-1].page)

        def _col_text(name: str) -> str:
            if name not in self._col_map:
                return ""
            toks = self._tokens_in_column(all_tokens, self._col_map[name], tolerance=10)
            return " ".join(t.text for t in toks).strip()

        txn.txn_date = _col_text("txn_date") or None
        txn.value_date = _col_text("value_date") or None
        txn.description = _col_text("remarks")
        txn.reference_no = _col_text("chq_no") or None
        wd = _col_text("withdrawal")
        if wd:
            txn.debit = TransactionValidator.parse_amount(wd)
        dp = _col_text("deposit")
        if dp:
            txn.credit = TransactionValidator.parse_amount(dp)
        bal = _col_text("balance")
        if bal:
            txn.balance = TransactionValidator.parse_amount(bal)
        return txn

    def _is_icici_header(self, text: str) -> bool:
        t = text.lower()
        return ("date" in t and "remark" in t) or ("transaction" in t and "balance" in t)

    def _is_icici_footer(self, text: str) -> bool:
        for p in [r"Closing\s+Balance", r"Total", r"computer\s+generated"]:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    def _calibrate_columns(self, header_line: ExtractedLine) -> None:
        for token in header_line.tokens:
            text = token.text.strip().lower()
            mapping = {"s no": "sno", "value": "value_date", "transaction": "txn_date",
                       "cheque": "chq_no", "remark": "remarks", "withdrawal": "withdrawal",
                       "deposit": "deposit", "balance": "balance"}
            for kw, col in mapping.items():
                if kw in text and col in self._col_map:
                    c = self._col_map[col]
                    self._col_map[col] = ColumnConfig(name=c.name, x_start=token.x0,
                                                       x_end=c.x_end, required=c.required)
