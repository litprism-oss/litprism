"""Exceptions for litprism-screen."""


class ScreeningError(Exception):
    def __init__(self, article_id: str, cause: Exception) -> None:
        self.article_id = article_id
        self.cause = cause
        super().__init__(f"Screening failed for {article_id}: {cause}")
