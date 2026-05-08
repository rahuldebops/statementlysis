"""Application-level exceptions."""


class LedgerLenseError(Exception):
    """Base exception for the application."""
    pass


class PDFExtractionError(LedgerLenseError):
    """Failed to extract content from PDF."""
    pass


class PDFPasswordRequired(LedgerLenseError):
    """PDF is password-protected and no password was provided."""
    pass


class PDFPasswordIncorrect(LedgerLenseError):
    """Provided password is incorrect."""
    pass


class BankDetectionError(LedgerLenseError):
    """Could not detect the bank from the statement."""
    pass


class ParserNotFoundError(LedgerLenseError):
    """No parser registered for the detected bank."""
    pass


class ParserError(LedgerLenseError):
    """Error during parsing/extraction."""
    pass


class ValidationError(LedgerLenseError):
    """Transaction validation failed."""
    pass


class DocumentNotFoundError(LedgerLenseError):
    """Requested document not found."""
    pass


class DuplicateDocumentError(LedgerLenseError):
    """Document with same SHA256 already exists."""
    pass
