"""Screener — concurrency-bounded batch screening with retry and error isolation."""

import asyncio
from datetime import UTC, datetime
from typing import Literal

from litprism.screen.criteria import Criteria
from litprism.screen.exceptions import ScreeningError
from litprism.screen.grounding import (
    _extract_json,
    _LLMResponse,
    derive_decision,
    validate_and_build,
)
from litprism.screen.llm import AzureOpenAIConfig, LLMConfig, _get_timeout, call_llm
from litprism.screen.llm import from_env as _llm_from_env
from litprism.screen.models import ScreenableArticle, ScreeningResult
from litprism.screen.prompts import build_prompt

# A reply that isn't parseable JSON is retried this many times in total.
_MAX_ATTEMPTS = 2


class Screener:
    def __init__(self, llm_config: LLMConfig, concurrency: int = 10) -> None:
        self._config = llm_config
        self._sem = asyncio.Semaphore(concurrency)

    @classmethod
    def from_env(cls, concurrency: int = 10) -> "Screener":
        """Construct a Screener from environment variables."""
        return cls(_llm_from_env(), concurrency)

    async def _ask(self, prompt: str) -> _LLMResponse:
        """Call the LLM and parse its JSON reply.

        Models occasionally return syntactically broken JSON. The next generation almost
        always parses, so retry once instead of recording a permanent error. Transport
        failures are not retried here (see llm._call_with_retry).
        """
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            raw = await asyncio.wait_for(
                call_llm(self._config, prompt),
                timeout=_get_timeout(self._config) + 5,  # belt-and-suspenders outer guard
            )
            try:
                return _LLMResponse.model_validate_json(_extract_json(raw))
            except ValueError:  # includes pydantic.ValidationError
                if attempt == _MAX_ATTEMPTS:
                    raise
        raise AssertionError("unreachable")  # pragma: no cover

    async def _screen_one(
        self,
        article: ScreenableArticle,
        criteria: Criteria,
        stage: Literal["abstract", "fulltext"],
    ) -> ScreeningResult:
        """Screen a single article; raises ScreeningError on persistent failure."""
        # AzureOpenAIConfig has no .model field — the deployment name is the identifier.
        model_used = (
            self._config.azure_deployment
            if isinstance(self._config, AzureOpenAIConfig)
            else self._config.model
        )

        if article.abstract is None:
            return ScreeningResult(
                article_id=article.id,
                decision="uncertain",
                confidence=0.0,
                reasoning="No abstract available — routed to full-text review",
                criteria_hits=[],
                stage=stage,
                model_used=model_used,
                llm_provider=self._config.provider,
                screened_at=datetime.now(UTC),
                human_override=False,
            )

        async with self._sem:
            try:
                prompt = build_prompt(article, criteria, stage)
                llm_response = await self._ask(prompt)
                hits = validate_and_build(llm_response, article.title, article.abstract)
                decision = derive_decision(hits)
                return ScreeningResult(
                    article_id=article.id,
                    decision=decision,
                    confidence=llm_response.confidence,
                    reasoning=llm_response.reasoning,
                    criteria_hits=hits,
                    stage=stage,
                    model_used=model_used,
                    llm_provider=self._config.provider,
                    screened_at=datetime.now(UTC),
                )
            except Exception as exc:
                raise ScreeningError(article_id=article.id, cause=exc) from exc

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
        tasks = [self._screen_one(a, criteria, stage) for a in articles]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        results = [o for o in outcomes if isinstance(o, ScreeningResult)]
        errors = [o for o in outcomes if isinstance(o, ScreeningError)]
        return results, errors
