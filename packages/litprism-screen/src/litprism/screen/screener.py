"""Screener — concurrency-bounded batch screening with retry and error isolation."""

from typing import Literal

from litprism.screen.criteria import Criteria
from litprism.screen.exceptions import ScreeningError
from litprism.screen.llm import LLMConfig
from litprism.screen.models import ScreenableArticle, ScreeningResult


class Screener:
    def __init__(self, llm_config: LLMConfig, concurrency: int = 10) -> None:
        raise NotImplementedError

    @classmethod
    def from_env(cls, concurrency: int = 10) -> "Screener":
        """Construct a Screener from environment variables."""
        raise NotImplementedError

    async def _screen_one(
        self,
        article: ScreenableArticle,
        criteria: Criteria,
        stage: Literal["abstract", "fulltext"],
    ) -> ScreeningResult:
        """Screen a single article; raises ScreeningError on persistent failure."""
        raise NotImplementedError

    async def ascreen_batch(
        self,
        articles: list[ScreenableArticle],
        criteria: Criteria,
        stage: Literal["abstract", "fulltext"] = "abstract",
    ) -> tuple[list[ScreeningResult], list[ScreeningError]]:
        """
        Screen a batch of articles concurrently.

        Returns (results, errors). A failure on one article never aborts
        the rest of the batch.
        """
        raise NotImplementedError
