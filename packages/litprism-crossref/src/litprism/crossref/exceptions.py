"""Exceptions for litprism-crossref."""


class CrossrefError(Exception):
    """Base exception for all litprism-crossref errors."""


class CrossrefAPIError(CrossrefError):
    """Raised when the Crossref API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CrossrefRateLimitError(CrossrefAPIError):
    """Raised when the API rate limit is exceeded (HTTP 429)."""


class CrossrefNotFoundError(CrossrefAPIError):
    """Raised when the requested DOI is not found (HTTP 404)."""


class CrossrefParseError(CrossrefError):
    """Raised when an API response cannot be parsed."""


class CrossrefNetworkError(CrossrefError):
    """Raised when a network-level error occurs (timeout, connection refused)."""
