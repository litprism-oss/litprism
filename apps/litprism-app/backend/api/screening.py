from typing import Annotated

from db.engine import get_db
from db.models import Project
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from litprism.screen.criteria import Criteria
from litprism.screen.models import ReviewType as ScreenReviewType
from litprism.screen.screener import Screener
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import PreviewCriteriaHit, ScreeningPreviewRequest, ScreeningPreviewResult

router = APIRouter(prefix="/projects", tags=["screening"])

DB = Annotated[AsyncSession, Depends(get_db)]

NOT_IMPLEMENTED = JSONResponse(
    {"detail": "Not implemented — Session 7.3"},
    status_code=501,
)


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
# Screening run routes — 501 stubs (implemented in Session 7.3)
# ---------------------------------------------------------------------------


@router.post("/{project_id}/screening/run")
async def create_screening_run(project_id: str) -> JSONResponse:
    return NOT_IMPLEMENTED


@router.get("/{project_id}/screening/runs")
async def list_screening_runs(project_id: str) -> JSONResponse:
    return NOT_IMPLEMENTED


@router.get("/{project_id}/screening/runs/{run_id}")
async def get_screening_run(project_id: str, run_id: str) -> JSONResponse:
    return NOT_IMPLEMENTED


@router.post("/{project_id}/screening/runs/{run_id}/resume")
async def resume_screening_run(project_id: str, run_id: str) -> JSONResponse:
    return NOT_IMPLEMENTED


@router.post("/{project_id}/screening/runs/{run_id}/cancel")
async def cancel_screening_run(project_id: str, run_id: str) -> JSONResponse:
    return NOT_IMPLEMENTED
