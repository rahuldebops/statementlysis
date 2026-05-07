"""PDF Token Extraction Engine.

Converts PDF pages into structured Token objects with bounding box coordinates.
Uses pdfplumber as primary engine with pymupdf as fallback.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pdfplumber
import fitz  # pymupdf

from app.core.types import Token, PageData
from app.core.exceptions import PDFExtractionError, PDFPasswordRequired, PDFPasswordIncorrect
from app.config import settings

logger = logging.getLogger(__name__)


class PDFEngine:
    """Extracts tokens with coordinates from PDF files."""

    def __init__(self, min_token_length: int = 1):
        self.min_token_length = min_token_length

    def extract(self, pdf_path: str | Path, password: Optional[str] = None) -> list[PageData]:
        """Extract all pages from a PDF into PageData objects.

        Uses pdfplumber for coordinate-accurate word extraction.
        Falls back to pymupdf if pdfplumber fails on a page.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise PDFExtractionError(f"PDF file not found: {pdf_path}")

        pages: list[PageData] = []

        try:
            pages = self._extract_with_pdfplumber(pdf_path, password)
        except PDFPasswordRequired:
            raise
        except PDFPasswordIncorrect:
            raise
        except Exception as e:
            logger.warning(f"pdfplumber failed, falling back to pymupdf: {e}")
            pages = self._extract_with_pymupdf(pdf_path, password)

        if not pages:
            raise PDFExtractionError("No pages extracted from PDF")

        logger.info(f"Extracted {len(pages)} pages, total tokens: {sum(len(p.tokens) for p in pages)}")
        return pages

    def _extract_with_pdfplumber(
        self, pdf_path: Path, password: Optional[str] = None
    ) -> list[PageData]:
        """Primary extraction using pdfplumber for precise coordinate data."""
        pages: list[PageData] = []

        try:
            pdf = pdfplumber.open(pdf_path, password=password or None)
        except Exception as e:
            err_msg = str(e).lower()
            if "password" in err_msg or "encrypted" in err_msg:
                if password:
                    raise PDFPasswordIncorrect(f"Incorrect password for {pdf_path.name}")
                raise PDFPasswordRequired(f"PDF is password-protected: {pdf_path.name}")
            raise

        with pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_number = page_idx + 1
                tokens: list[Token] = []
                raw_text = page.extract_text() or ""

                words = page.extract_words(
                    x_tolerance=3,
                    y_tolerance=3,
                    keep_blank_chars=False,
                    use_text_flow=False,
                    extra_attrs=["fontname", "size"],
                )

                for seq, word in enumerate(words):
                    text = word.get("text", "").strip()
                    if len(text) < self.min_token_length:
                        continue

                    token = Token(
                        text=text,
                        x0=round(float(word["x0"]), 2),
                        x1=round(float(word["x1"]), 2),
                        y0=round(float(word["top"]), 2),
                        y1=round(float(word["bottom"]), 2),
                        page=page_number,
                        sequence=seq,
                    )
                    tokens.append(token)

                pages.append(PageData(
                    page_number=page_number,
                    width=round(float(page.width), 2),
                    height=round(float(page.height), 2),
                    raw_text=raw_text,
                    tokens=tokens,
                ))

                logger.debug(
                    f"Page {page_number}: {len(tokens)} tokens extracted "
                    f"({page.width:.0f}x{page.height:.0f})"
                )

        return pages

    def _extract_with_pymupdf(
        self, pdf_path: Path, password: Optional[str] = None
    ) -> list[PageData]:
        """Fallback extraction using PyMuPDF."""
        pages: list[PageData] = []

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            raise PDFExtractionError(f"Failed to open PDF with pymupdf: {e}")

        if doc.is_encrypted:
            if not password:
                doc.close()
                raise PDFPasswordRequired(f"PDF is password-protected: {pdf_path.name}")
            if not doc.authenticate(password):
                doc.close()
                raise PDFPasswordIncorrect(f"Incorrect password for {pdf_path.name}")

        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_number = page_idx + 1
                tokens: list[Token] = []
                raw_text = page.get_text("text") or ""

                # Extract words with positions: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
                word_list = page.get_text("words")

                for seq, w in enumerate(word_list):
                    text = w[4].strip()
                    if len(text) < self.min_token_length:
                        continue

                    token = Token(
                        text=text,
                        x0=round(float(w[0]), 2),
                        y0=round(float(w[1]), 2),
                        x1=round(float(w[2]), 2),
                        y1=round(float(w[3]), 2),
                        page=page_number,
                        sequence=seq,
                    )
                    tokens.append(token)

                rect = page.rect
                pages.append(PageData(
                    page_number=page_number,
                    width=round(float(rect.width), 2),
                    height=round(float(rect.height), 2),
                    raw_text=raw_text,
                    tokens=tokens,
                ))

                logger.debug(f"Page {page_number} (pymupdf): {len(tokens)} tokens")
        finally:
            doc.close()

        return pages
