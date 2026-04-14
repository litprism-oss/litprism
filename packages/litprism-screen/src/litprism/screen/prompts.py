"""Prompt construction for LLM screening calls."""

from typing import Literal

from litprism.screen.criteria import Criteria
from litprism.screen.models import ScreenableArticle


def build_prompt(
    article: ScreenableArticle,
    criteria: Criteria,
    stage: Literal["abstract", "fulltext"],
) -> str:
    """Build the screening prompt for a single article."""
    raise NotImplementedError
