from sqlalchemy.ext.asyncio import AsyncSession


async def get_unscreened_articles(
    project_id: str,
    criteria_id: str,
    db: AsyncSession,
) -> list:
    """
    Returns Article rows with no ScreeningResult for the given criteria_id.
    Identical for fresh runs and resumes — the DB is the source of truth.
    Implemented in Session 7.3.
    """
    raise NotImplementedError


async def write_tombstone(
    article_id: str,
    project_id: str,
    criteria_id: str,
    cause: str,
    db: AsyncSession,
) -> None:
    """
    Writes a ScreeningResult with decision="uncertain", confidence=0.0,
    reasoning=f"Screening failed: {cause}". Marks the article as handled
    so it is never re-queued on resume. Implemented in Session 7.3.
    """
    raise NotImplementedError
