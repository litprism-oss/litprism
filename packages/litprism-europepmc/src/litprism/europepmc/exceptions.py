"""Exceptions for litprism-europepmc."""


class EuropePMCError(Exception):
    """Base exception for all litprism-europepmc errors."""


class EuropePMCAPIError(EuropePMCError):
    """Raised when the Europe PMC REST API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class EuropePMCRateLimitError(EuropePMCAPIError):
    """Raised when the API rate limit is exceeded (HTTP 429)."""


class EuropePMCParseError(EuropePMCError):
    """Raised when an API response cannot be parsed."""


class EuropePMCNetworkError(EuropePMCError):
    """Raised when a network-level error occurs (timeout, connection refused)."""
