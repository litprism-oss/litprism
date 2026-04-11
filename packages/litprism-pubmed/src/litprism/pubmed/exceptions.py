"""Exceptions for litprism-pubmed."""


class PubMedError(Exception):
    """Base exception for all litprism-pubmed errors."""


class PubMedAPIError(PubMedError):
    """Raised when the NCBI E-utilities API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PubMedRateLimitError(PubMedAPIError):
    """Raised when the API rate limit is exceeded (HTTP 429)."""


class PubMedParseError(PubMedError):
    """Raised when an API response cannot be parsed."""


class PubMedNetworkError(PubMedError):
    """Raised when a network-level error occurs (timeout, connection refused)."""
