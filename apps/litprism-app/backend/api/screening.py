import uuid
from datetime import UTC, datetime
from typing import Annotated

from db.engine import get_db
from db.models import Article, Project, ScreeningResult, ScreeningRun
from db.models import Criteria as DBCriteria
from fastapi import APIRouter, Depends, HTTPException, Query, status
from litprism.screen.criteria import Criteria
from litprism.screen.models import ReviewType as ScreenReviewType
from litprism.screen.screener import Screener
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tasks.screening import screen_coordinator

from api.schemas import (
    ArticleWithResult,
    ArticleWithResultListOut,
    CriteriaHitOut,
    FulltextScreeningEligibilityOut,
    HumanOverrideRequest,
    PreviewCriteriaHit,
    RetryFailedOut,
    ScreeningPreviewRequest,
    ScreeningPreviewResult,
    ScreeningResultOut,
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

    # Compute include counts per run. Legacy rows (screening_run_id IS NULL) are
    # attributed to the run whose criteria_id matches — fallback for pre-migration data.
    out = []
    for run in runs:
        obj = ScreeningRunOut.model_validate(run)
        n = await db.scalar(
            select(func.count())
            .where(ScreeningResult.project_id == project_id)
            .where(ScreeningResult.decision == "include")
            .where(
                (ScreeningResult.screening_run_id == run.id)
                | (
                    ScreeningResult.screening_run_id.is_(None)
                    & (ScreeningResult.criteria_id == run.criteria_id)
                )
            )
        )
        obj.included_count = n or 0
        out.append(obj)
    return out


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
    if run.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot resume a completed run",
        )
    run.status = "pending"
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


@router.delete("/{project_id}/screening/runs/{run_id}", status_code=204)
async def delete_screening_run(
    project_id: str,
    run_id: str,
    db: DB,
) -> None:
    run = await db.get(ScreeningRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
    if run.status in ("running", "pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a run that is currently active — pause it first",
        )
    # Delete associated results then the run itself
    results = (
        await db.scalars(select(ScreeningResult).where(ScreeningResult.screening_run_id == run_id))
    ).all()
    for r in results:
        await db.delete(r)
    await db.delete(run)
    await db.commit()


@router.post("/{project_id}/screening/runs/{run_id}/cancel", response_model=ScreeningRunOut)
async def cancel_screening_run(
    project_id: str,
    run_id: str,
    db: DB,
) -> ScreeningRunOut:
    run = await db.get(ScreeningRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
    if run.status in ("completed", "paused"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot pause a run with status '{run.status}'",
        )
    run.status = "paused"
    await db.commit()
    return run


# ---------------------------------------------------------------------------
# Screening results + override (Session 10.4)
# ---------------------------------------------------------------------------


def _effective_decision(sr: ScreeningResult) -> str:
    return sr.human_decision if sr.human_override and sr.human_decision else sr.decision


def _result_to_out(sr: ScreeningResult) -> ScreeningResultOut:
    hits = [CriteriaHitOut(**h) for h in (sr.criteria_hits or [])]
    return ScreeningResultOut(
        article_id=sr.article_id,
        decision=_effective_decision(sr),
        confidence=sr.confidence,
        reasoning=sr.reasoning,
        criteria_hits=hits,
        stage=sr.stage,
        model_used=sr.model_used,
        screened_at=sr.screened_at,
        human_override=sr.human_override,
        human_decision=sr.human_decision,
        human_note=sr.human_note,
    )


@router.get("/{project_id}/screening/results", response_model=ArticleWithResultListOut)
async def list_screening_results(
    project_id: str,
    db: DB,
    run_id: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> ArticleWithResultListOut:
    """Return project articles with their screening result for a specific run (or latest)."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Subquery: latest screening_result id per article, optionally scoped to a run.
    # Legacy rows (screening_run_id IS NULL) are attributed to the run whose criteria_id
    # matches — fallback for results written before the migration added this column.
    sr_filter = ScreeningResult.project_id == project_id
    if run_id:
        target_run = await db.get(ScreeningRun, run_id)
        if target_run is None or target_run.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found"
            )
        sr_filter = sr_filter & (
            (ScreeningResult.screening_run_id == run_id)
            | (
                ScreeningResult.screening_run_id.is_(None)
                & (ScreeningResult.criteria_id == target_run.criteria_id)
            )
        )

    latest_sr_subq = (
        select(
            ScreeningResult.article_id,
            func.max(ScreeningResult.screened_at).label("max_screened_at"),
        )
        .where(sr_filter)
        .group_by(ScreeningResult.article_id)
        .subquery()
    )

    # Join articles → latest screening result
    base_q = (
        select(Article, ScreeningResult)
        .outerjoin(
            latest_sr_subq,
            Article.id == latest_sr_subq.c.article_id,
        )
        .outerjoin(
            ScreeningResult,
            (ScreeningResult.article_id == latest_sr_subq.c.article_id)
            & (ScreeningResult.screened_at == latest_sr_subq.c.max_screened_at),
        )
        .where(Article.project_id == project_id)
    )

    if decision:
        has_override = ScreeningResult.human_override.is_(
            True
        ) & ScreeningResult.human_decision.isnot(None)
        effective = case(
            (has_override, ScreeningResult.human_decision),
            else_=ScreeningResult.decision,
        )
        base_q = base_q.where(effective == decision)

    total = await db.scalar(select(func.count()).select_from(base_q.subquery()))

    rows = (
        await db.execute(
            base_q.order_by(Article.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items: list[ArticleWithResult] = []
    for article, sr in rows:
        result_out = _result_to_out(sr) if sr is not None else None
        aw = ArticleWithResult.model_validate(article)
        aw.screening_result = result_out
        items.append(aw)

    return ArticleWithResultListOut(items=items, total=total or 0, page=page, page_size=page_size)


@router.post(
    "/{project_id}/screening/runs/{run_id}/retry-failed",
    status_code=202,
    response_model=RetryFailedOut,
)
async def retry_failed_screening(
    project_id: str,
    run_id: str,
    db: DB,
) -> RetryFailedOut:
    """
    Delete error tombstones from a run and re-queue those articles in a new screening run.
    Error tombstones have decision='error' and model_used='error'.
    Deleting them makes the articles visible to get_unscreened_articles again.
    """
    run = await db.get(ScreeningRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")

    # Find error tombstones scoped to this run's criteria version
    error_results = (
        await db.scalars(
            select(ScreeningResult)
            .where(ScreeningResult.project_id == project_id)
            .where(ScreeningResult.criteria_id == run.criteria_id)
            .where(ScreeningResult.decision == "error")
        )
    ).all()

    if not error_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No failed articles found for this run",
        )

    # Delete tombstones — articles become unscreened again
    for er in error_results:
        await db.delete(er)
    await db.flush()

    # Create a new run to track the retry
    retry_run = ScreeningRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        criteria_id=run.criteria_id,
        stage=run.stage,
        status="pending",
        total_articles=len(error_results),
        screened_count=0,
        error_count=0,
        chunk_size=run.chunk_size,
        created_at=datetime.now(UTC),
    )
    db.add(retry_run)
    await db.commit()

    screen_coordinator.delay(retry_run.id)

    return RetryFailedOut(
        deleted=len(error_results),
        requeued=len(error_results),
        run_id=retry_run.id,
    )


@router.post("/{project_id}/screening/{article_id}/override", response_model=ScreeningResultOut)
async def override_screening_decision(
    project_id: str,
    article_id: str,
    body: HumanOverrideRequest,
    db: DB,
) -> ScreeningResultOut:
    """Apply a human override to the latest screening result for an article."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    sr = (
        await db.scalars(
            select(ScreeningResult)
            .where(ScreeningResult.project_id == project_id)
            .where(ScreeningResult.article_id == article_id)
            .order_by(ScreeningResult.screened_at.desc())
            .limit(1)
        )
    ).first()

    if sr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No screening result found for this article",
        )

    sr.human_override = True
    sr.human_decision = body.decision
    sr.human_note = body.note
    sr.overridden_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(sr)
    return _result_to_out(sr)


# ---------------------------------------------------------------------------
# Full-text screening (Session 15)
# ---------------------------------------------------------------------------


async def _get_active_criteria(project_id: str, db: AsyncSession) -> DBCriteria | None:
    return (
        await db.scalars(
            select(DBCriteria)
            .where(DBCriteria.project_id == project_id)
            .where(DBCriteria.superseded_at.is_(None))
            .order_by(DBCriteria.version.desc())
            .limit(1)
        )
    ).first()


async def _fulltext_eligibility_counts(
    project_id: str, db: AsyncSession
) -> FulltextScreeningEligibilityOut:
    """
    Count uncertain articles (from abstract screening) broken down by
    full-text retrieval status.
    """
    rows = (
        await db.execute(
            select(Article.fulltext_status, func.count(Article.id).label("n"))
            .join(ScreeningResult, ScreeningResult.article_id == Article.id)
            .where(
                Article.project_id == project_id,
                ScreeningResult.decision == "uncertain",
                ScreeningResult.stage == "abstract",
            )
            .group_by(Article.fulltext_status)
            .distinct()
        )
    ).all()

    counts: dict[str | None, int] = {r.fulltext_status: r.n for r in rows}
    retrieved = counts.get("retrieved", 0)
    unavailable = counts.get("unavailable", 0)
    uncertain_total = sum(counts.values())

    return FulltextScreeningEligibilityOut(
        eligible=retrieved,
        uncertain_total=uncertain_total,
        retrieved=retrieved,
        unavailable=unavailable,
    )


@router.get(
    "/{project_id}/screening/fulltext-eligibility",
    response_model=FulltextScreeningEligibilityOut,
)
async def get_fulltext_eligibility(
    project_id: str,
    db: DB,
) -> FulltextScreeningEligibilityOut:
    """Returns counts to inform the full-text screening UI."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await _fulltext_eligibility_counts(project_id, db)


@router.post(
    "/{project_id}/screening/fulltext-run",
    status_code=202,
    response_model=ScreeningRunOut,
)
async def start_fulltext_screening(
    project_id: str,
    body: ScreeningRunCreate,
    db: DB,
) -> ScreeningRunOut:
    """
    Start a full-text screening run targeting uncertain articles that have
    retrieved full text available.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    criteria = await _get_active_criteria(project_id, db)
    if criteria is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active criteria — set up criteria first",
        )

    eligibility = await _fulltext_eligibility_counts(project_id, db)
    if eligibility.eligible == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No articles ready for full-text screening. Run full-text retrieval first.",
        )

    run = ScreeningRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        criteria_id=criteria.id,
        stage="fulltext",
        status="pending",
        total_articles=eligibility.eligible,
        screened_count=0,
        error_count=0,
        chunk_size=body.chunk_size,
        created_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()

    screen_coordinator.delay(run.id)
    return run
