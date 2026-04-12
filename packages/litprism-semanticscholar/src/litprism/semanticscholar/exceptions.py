"""Exceptions for litprism-semanticscholar."""


class SemanticScholarError(Exception):
    """Base exception for all litprism-semanticscholar errors."""


class SemanticScholarAPIError(SemanticScholarError):
    """Raised when the Semantic Scholar API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SemanticScholarRateLimitError(SemanticScholarAPIError):
    """Raised when the API rate limit is exceeded (HTTP 429)."""


class SemanticScholarParseError(SemanticScholarError):
    """Raised when an API response cannot be parsed."""


class SemanticScholarNetworkError(SemanticScholarError):
    """Raised when a network-level error occurs (timeout, connection refused)."""
