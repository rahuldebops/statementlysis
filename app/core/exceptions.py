"""Application-level exceptions."""


class StatementlysisError(Exception):
    """Base exception for the application."""
    pass


class PDFExtractionError(StatementlysisError):
    """Failed to extract content from PDF."""
    pass


class PDFPasswordRequired(StatementlysisError):
    """PDF is password-protected and no password was provided."""
    pass


class PDFPasswordIncorrect(StatementlysisError):
    """Provided password is incorrect."""
    pass


class BankDetectionError(StatementlysisError):
    """Could not detect the bank from the statement."""
    pass


class ParserNotFoundError(StatementlysisError):
    """No parser registered for the detected bank."""
    pass


class ParserError(StatementlysisError):
    """Error during parsing/extraction."""
    pass


class ValidationError(StatementlysisError):
    """Transaction validation failed."""
    pass


class DocumentNotFoundError(StatementlysisError):
    """Requested document not found."""
    pass


class DuplicateDocumentError(StatementlysisError):
    """Document with same SHA256 already exists."""
    pass
