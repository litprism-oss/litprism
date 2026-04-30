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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

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


@router.get("/{project_id}/export/prisma-s")
async def export_prisma_s(project_id: str, db: DB) -> Response:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Source queries across all search runs
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

    # Upload records
    ur_result = await db.execute(
        select(UploadRecord)
        .where(UploadRecord.project_id == project_id)
        .order_by(UploadRecord.uploaded_at)
    )
    upload_records = list(ur_result.scalars())

    # Counts
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
    records_screened = 0
    if active_criteria:
        sr_count_result = await db.execute(
            select(func.count()).where(
                ScreeningResult.project_id == project_id,
                ScreeningResult.criteria_id == active_criteria.id,
            )
        )
        records_screened = sr_count_result.scalar_one() or 0

    prisma_counts = {
        "db_records": sum(sq.result_count or 0 for sq in source_queries),
        "other_records": sum(ur.record_count or 0 for ur in upload_records),
        "duplicates_removed": duplicates_removed,
        "records_screened": records_screened,
    }

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
