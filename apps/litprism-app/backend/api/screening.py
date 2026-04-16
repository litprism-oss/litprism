import uuid
from datetime import UTC, datetime
from typing import Annotated

from db.engine import get_db
from db.models import Article, Project, ScreeningRun
from db.models import Criteria as DBCriteria
from fastapi import APIRouter, Depends, HTTPException, status
from litprism.screen.criteria import Criteria
from litprism.screen.models import ReviewType as ScreenReviewType
from litprism.screen.screener import Screener
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tasks.screening import screen_coordinator

from api.schemas import (
    PreviewCriteriaHit,
    ScreeningPreviewRequest,
    ScreeningPreviewResult,
    ScreeningRunCreate,
    ScreeningRunOut,
    ScreeningRunUpdate,
)

router = APIRouter(prefix="/projects", tags=["screening"])

DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/{project_id}/screening/preview", response_model=list[ScreeningPreviewResult])
async def screening_preview(
    project_id: str,
    body: ScreeningPreviewRequest,
    db: DB,
) -> list[ScreeningPreviewResult]:
    # 1. Load project (404 if not found)
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # 2. Build screen-package Criteria
    criteria = Criteria(
        review_type=ScreenReviewType(project.review_type),
        inclusion=body.criteria.inclusion,
        exclusion=body.criteria.exclusion,
    )

    # 3. Build screener
    screener = Screener.from_env()

    # 4. body.articles satisfies ScreenableArticle (Protocol: id, title, abstract)
    results, errors = await screener.ascreen_batch(body.articles, criteria, stage="abstract")

    # 5. Map ScreeningResult → ScreeningPreviewResult
    output: list[ScreeningPreviewResult] = []

    for result in results:
        hits = [
            PreviewCriteriaHit(
                criterion=hit.criterion,
                criterion_type=hit.criterion_type,
                assessment=hit.assessment,
                supporting_quote=hit.supporting_quote,
                unassessable_reason=hit.unassessable_reason,
            )
            for hit in result.criteria_hits
        ]
        output.append(
            ScreeningPreviewResult(
                article_id=result.article_id,
                decision=result.decision,
                confidence=result.confidence,
                reasoning=result.reasoning,
                criteria_hits=hits,
                model_used=result.model_used,
            )
        )

    # 6. Map errors → uncertain tombstone results (no DB write)
    for error in errors:
        output.append(
            ScreeningPreviewResult(
                article_id=error.article_id,
                decision="uncertain",
                confidence=0.0,
                reasoning=str(error.cause),
                criteria_hits=[],
                model_used="error",
            )
        )

    return output


# ---------------------------------------------------------------------------
# Screening run routes
# ---------------------------------------------------------------------------


@router.post("/{project_id}/screening/run", status_code=202, response_model=ScreeningRunOut)
async def create_or_resume_screening_run(
    project_id: str,
    body: ScreeningRunCreate,
    db: DB,
) -> ScreeningRunOut:
    """
    Creates a new screening run or resumes an existing incomplete one.
    If an incomplete run exists for the active criteria + stage, re-dispatches
    screen_coordinator. Otherwise creates a new ScreeningRun row.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Load active criteria (superseded_at IS NULL, highest version).
    active_criteria = (
        await db.scalars(
            select(DBCriteria)
            .where(DBCriteria.project_id == project_id)
            .where(DBCriteria.superseded_at.is_(None))
            .order_by(DBCriteria.version.desc())
            .limit(1)
        )
    ).first()
    if active_criteria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active criteria found — create criteria before screening",
        )

    # Find an existing incomplete run for this criteria version + stage.
    existing_run = (
        await db.scalars(
            select(ScreeningRun)
            .where(ScreeningRun.project_id == project_id)
            .where(ScreeningRun.criteria_id == active_criteria.id)
            .where(ScreeningRun.stage == body.stage)
            .where(ScreeningRun.status.in_(["pending", "running", "paused"]))
            .limit(1)
        )
    ).first()

    if existing_run is not None:
        existing_run.resumed_at = datetime.now(UTC)
        await db.commit()
        screen_coordinator.delay(existing_run.id)
        return existing_run

    # Count articles in this project for the total_articles field.
    total_articles = (
        await db.scalar(select(func.count(Article.id)).where(Article.project_id == project_id))
    ) or 0

    new_run = ScreeningRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        criteria_id=active_criteria.id,
        stage=body.stage,
        status="pending",
        total_articles=total_articles,
        screened_count=0,
        error_count=0,
        chunk_size=body.chunk_size,
        created_at=datetime.now(UTC),
    )
    db.add(new_run)
    await db.commit()
    screen_coordinator.delay(new_run.id)
    return new_run


@router.get("/{project_id}/screening/runs", response_model=list[ScreeningRunOut])
async def list_screening_runs(
    project_id: str,
    db: DB,
) -> list[ScreeningRunOut]:
    runs = (
        await db.scalars(
            select(ScreeningRun)
            .where(ScreeningRun.project_id == project_id)
            .order_by(ScreeningRun.created_at.desc())
        )
    ).all()
    return list(runs)


@router.get("/{project_id}/screening/runs/{run_id}", response_model=ScreeningRunOut)
async def get_screening_run(
    project_id: str,
    run_id: str,
    db: DB,
) -> ScreeningRunOut:
    run = await db.get(ScreeningRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
    return run


@router.post(
    "/{project_id}/screening/runs/{run_id}/resume",
    status_code=202,
    response_model=ScreeningRunOut,
)
async def resume_screening_run(
    project_id: str,
    run_id: str,
    db: DB,
) -> ScreeningRunOut:
    run = await db.get(ScreeningRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
    if run.status in ("completed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot resume a run with status '{run.status}'",
        )
    run.resumed_at = datetime.now(UTC)
    await db.commit()
    screen_coordinator.delay(run.id)
    return run


@router.patch("/{project_id}/screening/runs/{run_id}", response_model=ScreeningRunOut)
async def update_screening_run(
    project_id: str,
    run_id: str,
    body: ScreeningRunUpdate,
    db: DB,
) -> ScreeningRunOut:
    run = await db.get(ScreeningRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(run, field, value)
    await db.commit()
    return run


@router.post("/{project_id}/screening/runs/{run_id}/cancel", response_model=ScreeningRunOut)
async def cancel_screening_run(
    project_id: str,
    run_id: str,
    db: DB,
) -> ScreeningRunOut:
    run = await db.get(ScreeningRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
    if run.status in ("completed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a run with status '{run.status}'",
        )
    run.status = "cancelled"
    await db.commit()
    return run
