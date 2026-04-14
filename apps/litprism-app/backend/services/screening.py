from db.models import Article, Criteria, ScreeningResult
from sqlalchemy.ext.asyncio import AsyncSession


async def get_unscreened_articles(
    project_id: str,
    criteria: Criteria,
    db: AsyncSession,
) -> list[Article]:
    """Return articles that have no screening_results row for the given criteria."""
    raise NotImplementedError


async def write_tombstone(
    article: Article,
    criteria: Criteria,
    stage: str,
    cause: str,
    db: AsyncSession,
) -> ScreeningResult:
    """Persist a failed-screening tombstone so the article is never re-queued."""
    raise NotImplementedError
