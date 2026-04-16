from typing import Annotated, Literal

from db.engine import get_db
from db.models import Project
from fastapi import APIRouter, Depends, HTTPException, Query
from services.export import export_articles
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
    "prisma-s": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


@router.get("/{project_id}/export/{fmt}")
async def export(
    project_id: str,
    fmt: Literal["ris", "nbib", "csv", "json", "asreview", "prisma-s"],
    db: DB,
    decision: str | None = Query(None),
) -> Response:
    # Verify project exists
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    file_bytes, filename = await export_articles(project_id, db, decision, fmt)

    return Response(
        content=file_bytes,
        media_type=_CONTENT_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
