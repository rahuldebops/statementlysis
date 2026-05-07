"""Security utilities — hashing, masking."""

import hashlib
import re
from typing import Optional


def sha256_file(file_bytes: bytes) -> str:
    """Compute SHA256 hash of file content."""
    return hashlib.sha256(file_bytes).hexdigest()


def hash_password(password: str) -> str:
    """Hash a PDF password for storage (not for auth — just for record-keeping)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def mask_account_number(account_no: str) -> str:
    """Mask account number, showing only last 4 digits."""
    if len(account_no) <= 4:
        return account_no
    return "X" * (len(account_no) - 4) + account_no[-4:]


def mask_card_number(card_no: str) -> str:
    """Mask card number to show only last 4 digits."""
    digits = re.sub(r"\D", "", card_no)
    if len(digits) <= 4:
        return card_no
    masked = "XXXX-XXXX-XXXX-" + digits[-4:]
    return masked


def mask_ifsc(ifsc: str, mask: bool = False) -> str:
    """Optionally mask IFSC code."""
    if not mask or len(ifsc) < 4:
        return ifsc
    return ifsc[:4] + "XXXXXXX"
