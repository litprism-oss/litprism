import asyncio
import logging

from config import settings

from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def enrich_articles_task(self, project_id: str, article_ids: list[str]) -> dict:
    """Background task to enrich articles with missing abstracts."""
    from db.engine import AsyncSessionLocal
    from services.enrichment import enrich_articles

    async def _run():
        async with AsyncSessionLocal() as db:
            return await enrich_articles(project_id, article_ids, db, settings)

    try:
        result = asyncio.run(_run())
        logger.info("Enrichment task complete result=%s", result)
        return result
    except Exception as exc:
        logger.error("Enrichment task failed: %s", exc)
        raise self.retry(exc=exc, countdown=60) from exc
