import asyncio
import logging

from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def retrieve_fulltext_task(self, project_id: str) -> dict:
    """Background task to retrieve full text for uncertain articles in a project."""
    from db.engine import AsyncSessionLocal
    from services.fulltext import retrieve_fulltext_for_project

    async def _run():
        async with AsyncSessionLocal() as db:
            return await retrieve_fulltext_for_project(project_id, db)

    try:
        result = asyncio.run(_run())
        logger.info("Full text retrieval task complete: %s", result)
        return result
    except Exception as exc:
        logger.error("Full text retrieval task failed: %s", exc)
        raise self.retry(exc=exc, countdown=120) from exc
