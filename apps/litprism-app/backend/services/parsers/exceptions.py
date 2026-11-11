class ParseError(Exception):
    """Base class for all parser errors. Caught by the upload endpoint."""


class PasswordProtectedPDFError(ParseError):
    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(
            f"'{filename}' is password-protected and cannot be parsed. "
            "Please provide an unlocked PDF."
        )


class EmptyFileError(ParseError):
    """Raised when a PDF produces no extractable text — typically a scanned
    image-only document or a corrupted file."""

    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(
            f"'{filename}' contains no extractable text. "
            "Scanned PDFs require OCR preprocessing before upload."
        )
