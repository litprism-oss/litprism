from typing import Annotated

from db.engine import get_db
from db.models import Article
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tasks.fulltext import retrieve_fulltext_task

from api.schemas import FulltextStatusOut

router = APIRouter(prefix="/projects", tags=["fulltext"])

DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/{project_id}/fulltext/retrieve")
async def trigger_fulltext_retrieval(
    project_id: str,
    db: DB,
) -> dict:
    """Trigger background full-text retrieval for all articles not yet attempted."""
    result = await db.execute(
        select(func.count(Article.id)).where(
            Article.project_id == project_id,
            Article.fulltext_text.is_(None),
            Article.fulltext_status.is_(None),
        )
    )
    count = result.scalar()

    if count == 0:
        return {"queued": 0, "message": "No articles need full text retrieval"}

    retrieve_fulltext_task.delay(project_id)
    return {"queued": count, "message": f"Retrieval queued for {count} articles"}


@router.get("/{project_id}/fulltext/status")
async def get_fulltext_status(
    project_id: str,
    db: DB,
) -> FulltextStatusOut:
    """Returns full-text retrieval progress counts for a project."""
    result = await db.execute(select(Article).where(Article.project_id == project_id))
    articles = result.scalars().all()

    return FulltextStatusOut(
        total=len(articles),
        pending=sum(1 for a in articles if a.fulltext_status == "pending"),
        retrieved=sum(1 for a in articles if a.fulltext_status == "retrieved"),
        unavailable=sum(1 for a in articles if a.fulltext_status == "unavailable"),
        error=sum(1 for a in articles if a.fulltext_status == "error"),
        not_attempted=sum(1 for a in articles if a.fulltext_status is None),
    )
