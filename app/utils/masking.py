"""PII Masking utilities."""

import re


def mask_account_number(text: str) -> str:
    """Mask account numbers in text, keeping last 4 digits."""
    return re.sub(
        r"\b(\d{4})\d{4,}(\d{4})\b",
        lambda m: m.group(1) + "X" * (len(m.group(0)) - 8) + m.group(2),
        text,
    )


def mask_card_numbers(text: str) -> str:
    """Mask card numbers (16-digit patterns)."""
    return re.sub(
        r"\b(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b",
        r"\1-XXXX-XXXX-\4",
        text,
    )
