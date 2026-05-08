"""Bank Detection Engine.

Identifies the issuing bank from a PDF statement using pattern matching
on the first few pages. No ML — purely regex/keyword-based.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.core.types import PageData, BankDetectionResult, StatementType

logger = logging.getLogger(__name__)

# Bank detection patterns: bank_id → list of (pattern, weight)
BANK_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "hdfc": [
        (r"HDFC\s*BANK", 3.0),
        (r"hdfcbank\.com", 2.5),
        (r"HDFC\d{4}", 1.5),
        (r"IFSC\s*:?\s*HDFC", 2.0),
        (r"Housing Development Finance", 2.0),
    ],
    "sbi": [
        (r"State\s*Bank\s*of\s*India", 3.0),
        (r"SBI\s", 2.0),
        (r"sbi\.co\.in", 2.5),
        (r"IFSC\s*:?\s*SBIN", 2.0),
        (r"onlinesbi\.com", 2.0),
    ],
    "icici": [
        (r"ICICI\s*BANK", 3.0),
        (r"icicibank\.com", 2.5),
        (r"IFSC\s*:?\s*ICIC", 2.0),
        (r"Industrial\s*Credit\s*and\s*Investment", 2.0),
    ],
    "axis": [
        (r"AXIS\s*BANK", 3.0),
        (r"axisbank\.com", 2.5),
        (r"IFSC\s*:?\s*UTIB", 2.0),
    ],
    "kotak": [
        (r"KOTAK\s*MAHINDRA", 3.0),
        (r"kotak\.com", 2.5),
        (r"IFSC\s*:?\s*KKBK", 2.0),
    ],
    "bob": [
        (r"Bank\s*of\s*Baroda", 3.0),
        (r"bankofbaroda\.co\.in", 2.5),
        (r"IFSC\s*:?\s*BARB", 2.0),
    ],
    "pnb": [
        (r"Punjab\s*National\s*Bank", 3.0),
        (r"pnbindia\.in", 2.5),
        (r"IFSC\s*:?\s*PUNB", 2.0),
    ],
    "canara": [
        (r"CANARA\s*BANK", 3.0),
        (r"canarabank\.com", 2.5),
        (r"IFSC\s*:?\s*CNRB", 2.0),
    ],
    "indusind": [
        (r"IndusInd\s*Bank", 3.0),
        (r"indusind\.com", 2.5),
        (r"IFSC\s*:?\s*INDB", 2.0),
    ],
    "yes": [
        (r"YES\s*BANK", 3.0),
        (r"yesbank\.in", 2.5),
        (r"IFSC\s*:?\s*YESB", 2.0),
    ],
}

# Bank display names
BANK_NAMES: dict[str, str] = {
    "hdfc": "HDFC Bank",
    "sbi": "State Bank of India",
    "icici": "ICICI Bank",
    "axis": "Axis Bank",
    "kotak": "Kotak Mahindra Bank",
    "bob": "Bank of Baroda",
    "pnb": "Punjab National Bank",
    "canara": "Canara Bank",
    "indusind": "IndusInd Bank",
    "yes": "YES Bank",
}

# Statement type detection patterns
STATEMENT_TYPE_PATTERNS: dict[StatementType, list[str]] = {
    StatementType.SAVINGS: [
        r"Savings\s*Account",
        r"SB\s*A/C",
        r"Savings\s*Bank",
    ],
    StatementType.CURRENT: [
        r"Current\s*Account",
        r"CA\s*A/C",
        r"Current\s*A/C",
    ],
    StatementType.CREDIT_CARD: [
        r"Credit\s*Card",
        r"Card\s*Statement",
        r"Card\s*No",
        r"\d{4}\s*XXXX\s*XXXX\s*\d{4}",
    ],
    StatementType.WALLET: [
        r"Wallet\s*Statement",
        r"Paytm\s*Wallet",
        r"PhonePe",
    ],
    StatementType.PASSBOOK: [
        r"Passbook",
        r"Pass\s*Book",
    ],
}


class BankDetector:
    """Detects issuing bank and statement type from PDF content."""

    def __init__(self, pages_to_scan: int = 3):
        self.pages_to_scan = pages_to_scan

    def detect(self, pages: list[PageData]) -> BankDetectionResult:
        """Detect bank from the first N pages of extracted text."""
        scan_pages = pages[: self.pages_to_scan]
        combined_text = "\n".join(p.raw_text for p in scan_pages)

        bank_id, bank_confidence, matched = self._match_bank(combined_text)
        statement_type = self._detect_statement_type(combined_text)

        result = BankDetectionResult(
            bank_id=bank_id,
            bank_name=BANK_NAMES.get(bank_id, "") if bank_id else None,
            confidence=bank_confidence,
            matched_patterns=matched,
            statement_type=statement_type,
        )

        if bank_id:
            logger.info(
                f"Bank detected: {result.bank_name} (confidence={bank_confidence:.2f}, "
                f"patterns={len(matched)})"
            )
        else:
            logger.warning("No bank detected — will use generic parser")

        return result

    def _match_bank(self, text: str) -> tuple[Optional[str], float, list[str]]:
        """Score each bank against the text and return the best match."""
        scores: dict[str, float] = {}
        matches: dict[str, list[str]] = {}

        for bank_id, patterns in BANK_PATTERNS.items():
            bank_score = 0.0
            bank_matches: list[str] = []

            for pattern, weight in patterns:
                found = re.search(pattern, text, re.IGNORECASE)
                if found:
                    bank_score += weight
                    bank_matches.append(pattern)

            if bank_score > 0:
                scores[bank_id] = bank_score
                matches[bank_id] = bank_matches

        if not scores:
            return None, 0.0, []

        best_bank = max(scores, key=scores.get)  # type: ignore
        best_score = scores[best_bank]

        # Normalize confidence to 0-1 range (cap at 10 for normalization)
        confidence = min(best_score / 10.0, 1.0)

        return best_bank, round(confidence, 4), matches[best_bank]

    def _detect_statement_type(self, text: str) -> StatementType:
        """Detect statement type from text patterns."""
        for stmt_type, patterns in STATEMENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    logger.debug(f"Statement type detected: {stmt_type.value}")
                    return stmt_type

        return StatementType.UNKNOWN
