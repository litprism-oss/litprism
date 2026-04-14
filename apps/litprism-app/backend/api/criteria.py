from datetime import UTC, datetime
from typing import Annotated

from db.engine import get_db
from db.models import Article, Criteria, Project, ScreeningResult
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import CriteriaCreate, CriteriaOut, StaleCountOut

router = APIRouter(prefix="/projects/{project_id}", tags=["criteria"])

DB = Annotated[AsyncSession, Depends(get_db)]


async def _get_project_or_404(project_id: str, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _get_active_criteria(project_id: str, db: AsyncSession) -> Criteria | None:
    result = await db.execute(
        select(Criteria).where(Criteria.project_id == project_id, Criteria.superseded_at.is_(None))
    )
    return result.scalar_one_or_none()


@router.post("/criteria", response_model=CriteriaOut, status_code=status.HTTP_201_CREATED)
async def create_criteria(project_id: str, body: CriteriaCreate, db: DB) -> Criteria:
    await _get_project_or_404(project_id, db)

    now = datetime.now(UTC)

    # Supersede the active version if one exists.
    active = await _get_active_criteria(project_id, db)
    if active is not None:
        active.superseded_at = now

    # Determine next version number.
    max_result = await db.execute(
        select(func.max(Criteria.version)).where(Criteria.project_id == project_id)
    )
    max_version: int | None = max_result.scalar_one_or_none()
    new_version = 1 if max_version is None else max_version + 1

    criteria = Criteria(
        project_id=project_id,
        version=new_version,
        inclusion=body.inclusion,
        exclusion=body.exclusion,
        uncertain_threshold=body.uncertain_threshold,
        created_at=now,
        superseded_at=None,
    )
    db.add(criteria)
    await db.commit()
    await db.refresh(criteria)
    return criteria


@router.get("/criteria", response_model=CriteriaOut)
async def get_active_criteria(project_id: str, db: DB) -> Criteria:
    await _get_project_or_404(project_id, db)
    active = await _get_active_criteria(project_id, db)
    if active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active criteria")
    return active


# NOTE: /history must be registered before /{version} so FastAPI doesn't
# interpret the literal string "history" as a version integer.
@router.get("/criteria/history", response_model=list[CriteriaOut])
async def get_criteria_history(project_id: str, db: DB) -> list[Criteria]:
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(Criteria).where(Criteria.project_id == project_id).order_by(Criteria.version)
    )
    return list(result.scalars().all())


@router.get("/criteria/{version}", response_model=CriteriaOut)
async def get_criteria_by_version(project_id: str, version: int, db: DB) -> Criteria:
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(Criteria).where(
            Criteria.project_id == project_id,
            Criteria.version == version,
        )
    )
    criteria = result.scalar_one_or_none()
    if criteria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Criteria version {version} not found",
        )
    return criteria


@router.get("/screening/stale-count", response_model=StaleCountOut)
async def get_stale_count(project_id: str, db: DB) -> StaleCountOut:
    await _get_project_or_404(project_id, db)

    active = await _get_active_criteria(project_id, db)
    if active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active criteria")

    # Screening results whose criteria differ from the active version.
    stale_result = await db.execute(
        select(func.count())
        .select_from(ScreeningResult)
        .where(
            ScreeningResult.project_id == project_id,
            ScreeningResult.criteria_id != active.id,
        )
    )
    stale_results: int = stale_result.scalar_one()

    # Articles that have no screening_results row under the active criteria.
    screened_subq = (
        select(ScreeningResult.article_id)
        .where(ScreeningResult.criteria_id == active.id)
        .scalar_subquery()
    )
    unscreened_result = await db.execute(
        select(func.count())
        .select_from(Article)
        .where(
            Article.project_id == project_id,
            Article.id.not_in(screened_subq),
        )
    )
    unscreened: int = unscreened_result.scalar_one()

    # Total articles for the project.
    total_result = await db.execute(
        select(func.count()).select_from(Article).where(Article.project_id == project_id)
    )
    total_articles: int = total_result.scalar_one()

    return StaleCountOut(
        project_id=project_id,
        active_criteria_version=active.version,
        stale_results=stale_results,
        unscreened=unscreened,
        total_articles=total_articles,
    )
