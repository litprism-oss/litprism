import uuid
from datetime import UTC, datetime

from db.models import Article, ScreeningResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_unscreened_articles(
    project_id: str,
    criteria_id: str,
    db: AsyncSession,
) -> list[Article]:
    """
    Returns Article rows with no ScreeningResult for the given criteria_id.
    Identical for fresh runs and resumes — the DB is the source of truth.
    """
    stmt = (
        select(Article)
        .where(Article.project_id == project_id)
        .where(
            ~(
                select(ScreeningResult.id)
                .where(ScreeningResult.article_id == Article.id)
                .where(ScreeningResult.criteria_id == criteria_id)
                .correlate(Article)
                .exists()
            )
        )
        .order_by(Article.created_at)
    )
    return list((await db.scalars(stmt)).all())


async def write_tombstone(
    article_id: str,
    project_id: str,
    criteria_id: str,
    cause: str,
    db: AsyncSession,
    screening_run_id: str | None = None,
) -> None:
    """
    Writes a ScreeningResult tombstone for a persistently failing article.
    decision="uncertain", confidence=0.0. Marks the article as handled
    so it is never re-queued on resume.
    """
    tombstone = ScreeningResult(
        id=str(uuid.uuid4()),
        article_id=article_id,
        project_id=project_id,
        criteria_id=criteria_id,
        screening_run_id=screening_run_id,
        stage="abstract",
        decision="uncertain",
        confidence=0.0,
        reasoning=f"Screening failed: {cause}",
        criteria_hits=[],
        model_used="error",
        llm_provider="error",
        screened_at=datetime.now(UTC),
    )
    db.add(tombstone)
    await db.commit()
