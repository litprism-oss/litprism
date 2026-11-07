from datetime import date
from typing import Annotated, Literal

from db.engine import get_db
from db.models import (
    Criteria,
    DeduplicationLog,
    Project,
    ScreeningResult,
    SearchRun,
    SourceQuery,
    UploadRecord,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from services.export import export_articles, generate_prisma_s_docx
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from api.schemas import PRISMAFlowCountsOut

DB = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/projects", tags=["export"])

_CONTENT_TYPES = {
    "ris": "application/x-research-info-systems",
    "nbib": "text/plain",
    "csv": "text/csv",
    "json": "application/json",
    "asreview": "application/zip",
}

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _source_queries_and_uploads(
    project_id: str, db: AsyncSession
) -> tuple[list[SourceQuery], list[UploadRecord]]:
    runs_result = await db.execute(
        select(SearchRun).where(SearchRun.project_id == project_id).order_by(SearchRun.created_at)
    )
    run_ids = [r.id for r in runs_result.scalars()]
    source_queries: list[SourceQuery] = []
    if run_ids:
        sq_result = await db.execute(
            select(SourceQuery)
            .where(SourceQuery.search_run_id.in_(run_ids))
            .order_by(SourceQuery.searched_at)
        )
        source_queries = list(sq_result.scalars())

    ur_result = await db.execute(
        select(UploadRecord)
        .where(UploadRecord.project_id == project_id)
        .order_by(UploadRecord.uploaded_at)
    )
    return source_queries, list(ur_result.scalars())


async def _prisma_counts(
    project_id: str,
    source_queries: list[SourceQuery],
    upload_records: list[UploadRecord],
    db: AsyncSession,
) -> PRISMAFlowCountsOut:
    """
    PRISMA 2020 flow counts under the active criteria version. Human overrides win over
    the model's decision; error tombstones are not counted as screened.
    """
    dedup_result = await db.execute(
        select(func.count()).where(DeduplicationLog.project_id == project_id)
    )
    duplicates_removed: int = dedup_result.scalar_one() or 0

    active_criteria_result = await db.execute(
        select(Criteria)
        .where(Criteria.project_id == project_id, Criteria.superseded_at.is_(None))
        .order_by(Criteria.version.desc())
        .limit(1)
    )
    active_criteria = active_criteria_result.scalar_one_or_none()

    # (stage, decision) -> distinct article count
    by_decision: dict[tuple[str, str], int] = {}
    if active_criteria:
        effective = case(
            (
                ScreeningResult.human_override & ScreeningResult.human_decision.isnot(None),
                ScreeningResult.human_decision,
            ),
            else_=ScreeningResult.decision,
        )
        rows = await db.execute(
            select(
                ScreeningResult.stage,
                effective.label("decision"),
                func.count(ScreeningResult.article_id.distinct()),
            )
            .where(
                ScreeningResult.project_id == project_id,
                ScreeningResult.criteria_id == active_criteria.id,
                ScreeningResult.decision != "error",
            )
            .group_by(ScreeningResult.stage, effective)
        )
        by_decision = {(stage, decision): n for stage, decision, n in rows.all()}

    def stage_total(stage: str) -> int:
        return sum(n for (s, _), n in by_decision.items() if s == stage)

    has_fulltext = stage_total("fulltext") > 0

    return PRISMAFlowCountsOut(
        db_records=sum(sq.result_count or 0 for sq in source_queries),
        other_records=sum(ur.record_count or 0 for ur in upload_records),
        duplicates_removed=duplicates_removed,
        records_screened=stage_total("abstract"),
        excluded_screening=by_decision.get(("abstract", "exclude"), 0),
        uncertain=by_decision.get(("abstract", "uncertain"), 0),
        fulltext_assessed=stage_total("fulltext") if has_fulltext else None,
        fulltext_excluded=by_decision.get(("fulltext", "exclude"), 0) if has_fulltext else None,
        studies_included=(
            by_decision.get(("abstract", "include"), 0)
            + by_decision.get(("fulltext", "include"), 0)
        ),
    )


@router.get("/{project_id}/prisma-counts", response_model=PRISMAFlowCountsOut)
async def get_prisma_counts(project_id: str, db: DB) -> PRISMAFlowCountsOut:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    source_queries, upload_records = await _source_queries_and_uploads(project_id, db)
    return await _prisma_counts(project_id, source_queries, upload_records, db)


@router.get("/{project_id}/export/prisma-s")
async def export_prisma_s(project_id: str, db: DB) -> Response:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    source_queries, upload_records = await _source_queries_and_uploads(project_id, db)
    counts = await _prisma_counts(project_id, source_queries, upload_records, db)
    prisma_counts = counts.model_dump()

    docx_bytes = generate_prisma_s_docx(project, source_queries, upload_records, prisma_counts)
    safe_name = project.name.replace(" ", "_")
    filename = f"PRISMA-S_{safe_name}_{date.today()}.docx"

    return Response(
        content=docx_bytes,
        media_type=_DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/export/{fmt}")
async def export(
    project_id: str,
    fmt: Literal["ris", "nbib", "csv", "json", "asreview"],
    db: DB,
    decision: str | None = Query(None),
) -> Response:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    file_bytes, filename = await export_articles(project_id, db, decision, fmt)

    return Response(
        content=file_bytes,
        media_type=_CONTENT_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
