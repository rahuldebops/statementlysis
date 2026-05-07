"""Transaction Validation Engine.

Validates extracted transactions for correctness and assigns confidence scores.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.core.types import RawTransaction, FieldConfidence, TransactionType

logger = logging.getLogger(__name__)


class TransactionValidator:
    """Validates transactions and computes confidence scores."""

    # Common Indian date formats
    DATE_FORMATS = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d %b %Y",
        "%d %b %y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d %B %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]

    def validate_transactions(self, transactions: list[RawTransaction]) -> list[RawTransaction]:
        """Run all validations and update confidence scores."""
        for txn in transactions:
            txn.confidence = self._compute_confidence(txn)

        # Run balance continuity check across the full list
        self._validate_balance_continuity(transactions)

        return transactions

    def _compute_confidence(self, txn: RawTransaction) -> FieldConfidence:
        """Compute field-level confidence for a single transaction."""
        conf = FieldConfidence()

        # Date confidence
        conf.date = self._validate_date(txn.txn_date)

        # Description confidence
        conf.description = self._validate_description(txn.description)

        # Amount confidence
        conf.amount = self._validate_amount(txn)

        # Balance confidence
        conf.balance = self._validate_balance_value(txn.balance)

        return conf

    def _validate_date(self, date_str: Optional[str]) -> float:
        """Validate and score a date string."""
        if not date_str:
            return 0.0

        for fmt in self.DATE_FORMATS:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                # Sanity check: date should be within reasonable range
                if 2000 <= parsed.year <= 2030:
                    return 1.0
                return 0.5
            except ValueError:
                continue

        return 0.1  # Has text but doesn't match any format

    def _validate_description(self, description: str) -> float:
        """Score the quality of the description field."""
        if not description or not description.strip():
            return 0.0

        desc = description.strip()

        # Very short descriptions are suspicious
        if len(desc) < 3:
            return 0.3

        # Reasonable description
        if len(desc) >= 5:
            # Check if it looks like garbage (all numbers, special chars)
            alpha_ratio = sum(c.isalpha() for c in desc) / len(desc) if desc else 0
            if alpha_ratio < 0.2:
                return 0.4
            return 0.9

        return 0.6

    def _validate_amount(self, txn: RawTransaction) -> float:
        """Validate debit/credit amounts."""
        has_debit = txn.debit is not None and txn.debit > 0
        has_credit = txn.credit is not None and txn.credit > 0

        # Must have exactly one of debit or credit for non-credit-card statements
        if has_debit and has_credit:
            return 0.3  # Both set — unusual

        if not has_debit and not has_credit:
            return 0.1  # Neither set

        amount = txn.debit if has_debit else txn.credit
        if amount and amount > 0:
            # Set the transaction type
            if has_debit:
                txn.txn_type = TransactionType.DEBIT
            else:
                txn.txn_type = TransactionType.CREDIT
            return 0.95

        return 0.5

    def _validate_balance_value(self, balance: Optional[float]) -> float:
        """Check if balance looks valid."""
        if balance is None:
            return 0.0
        if balance >= 0:
            return 0.9
        return 0.5  # Negative balance — possible for overdraft

    def _validate_balance_continuity(self, transactions: list[RawTransaction]) -> None:
        """Check if balances flow correctly: prev_balance - debit + credit == current_balance.

        Updates confidence scores based on continuity.
        """
        if len(transactions) < 2:
            return

        for i in range(1, len(transactions)):
            prev = transactions[i - 1]
            curr = transactions[i]

            if prev.balance is None or curr.balance is None:
                continue

            debit = curr.debit or 0.0
            credit = curr.credit or 0.0
            expected = prev.balance - debit + credit

            if abs(expected - curr.balance) < 0.01:
                # Perfect continuity — boost confidence
                curr.confidence.balance = min(curr.confidence.balance + 0.1, 1.0)
                curr.confidence.amount = min(curr.confidence.amount + 0.05, 1.0)
            else:
                # Balance mismatch — reduce confidence
                curr.confidence.balance = max(curr.confidence.balance - 0.2, 0.0)
                logger.debug(
                    f"Balance discontinuity at txn {curr.sequence}: "
                    f"expected={expected:.2f}, got={curr.balance:.2f}"
                )

    @staticmethod
    def parse_date(date_str: str) -> Optional[date]:
        """Parse an Indian date string into a date object."""
        for fmt in TransactionValidator.DATE_FORMATS:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def parse_amount(amount_str: str) -> Optional[float]:
        """Parse an Indian currency amount string."""
        if not amount_str:
            return None

        # Remove commas, spaces, currency symbols
        cleaned = re.sub(r"[₹,\s]", "", amount_str.strip())

        # Handle Dr/Cr suffixes
        cleaned = re.sub(r"\s*(Dr|Cr|DR|CR)\.?\s*$", "", cleaned)

        try:
            value = float(cleaned)
            return round(value, 2)
        except (ValueError, InvalidOperation):
            return None
