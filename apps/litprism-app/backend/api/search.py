import uuid
from datetime import UTC, datetime
from typing import Annotated

from db.engine import AsyncSessionLocal, get_db
from db.models import Article, Project, SearchRun
from dependencies import get_ws_manager
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from services.pipeline import run_search
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ws import ConnectionManager

from api.schemas import ArticleListOut, ArticleOut, SearchRunCreate, SearchRunOut, SearchRunUpdate

router = APIRouter(tags=["search"])

DB = Annotated[AsyncSession, Depends(get_db)]
WS = Annotated[ConnectionManager, Depends(get_ws_manager)]


async def _get_run_or_404(
    run_id: str,
    project_id: str,
    db: AsyncSession,
) -> SearchRun:
    result = await db.execute(
        select(SearchRun)
        .where(SearchRun.id == run_id, SearchRun.project_id == project_id)
        .options(selectinload(SearchRun.source_queries))
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found")
    return run


async def _run_search_task(
    project_id: str,
    search_run_id: str,
    ws_manager: ConnectionManager,
) -> None:
    """Background task wrapper — opens its own DB session."""
    async with AsyncSessionLocal() as db:
        await run_search(project_id, search_run_id, db, ws_manager)


# ---------------------------------------------------------------------------
# Search run CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/search-runs",
    response_model=SearchRunOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_search_run(
    project_id: str,
    body: SearchRunCreate,
    db: DB,
) -> SearchRun:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    run = SearchRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        review_type=body.review_type,
        query_natural=body.query_natural,
        query_final=body.query_final,
        filters=body.filters,
        status="draft",
    )
    db.add(run)
    await db.commit()

    result = await db.execute(
        select(SearchRun)
        .where(SearchRun.id == run.id)
        .options(selectinload(SearchRun.source_queries))
    )
    return result.scalar_one()


@router.get("/projects/{project_id}/search-runs", response_model=list[SearchRunOut])
async def list_search_runs(project_id: str, db: DB) -> list[SearchRun]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(SearchRun)
        .where(SearchRun.project_id == project_id)
        .options(selectinload(SearchRun.source_queries))
        .order_by(SearchRun.created_at)
    )
    return list(result.scalars().all())


@router.get("/projects/{project_id}/search-runs/{run_id}", response_model=SearchRunOut)
async def get_search_run(project_id: str, run_id: str, db: DB) -> SearchRun:
    return await _get_run_or_404(run_id, project_id, db)


@router.patch("/projects/{project_id}/search-runs/{run_id}", response_model=SearchRunOut)
async def update_search_run(
    project_id: str,
    run_id: str,
    body: SearchRunUpdate,
    db: DB,
) -> SearchRun:
    run = await _get_run_or_404(run_id, project_id, db)
    if run.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update search run with status '{run.status}'",
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(run, field, value)
    await db.commit()

    result = await db.execute(
        select(SearchRun)
        .where(SearchRun.id == run_id)
        .options(selectinload(SearchRun.source_queries))
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/search-runs/{run_id}/execute",
    response_model=SearchRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_search_run(
    project_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    db: DB,
    ws_manager: WS,
) -> SearchRun:
    run = await _get_run_or_404(run_id, project_id, db)
    if run.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot execute search run with status '{run.status}'",
        )

    run.status = "locked"
    run.locked_at = datetime.now(UTC)
    await db.flush()
    await db.commit()

    background_tasks.add_task(_run_search_task, project_id, run_id, ws_manager)

    result = await db.execute(
        select(SearchRun)
        .where(SearchRun.id == run_id)
        .options(selectinload(SearchRun.source_queries))
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Articles list
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/search-runs/{run_id}/articles",
    response_model=ArticleListOut,
)
async def list_search_run_articles(
    project_id: str,
    run_id: str,
    db: DB,
    page: int = 1,
    page_size: int = 50,
) -> ArticleListOut:
    await _get_run_or_404(run_id, project_id, db)

    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count(Article.id)).where(Article.search_run_id == run_id)
    )
    total: int = total_result.scalar_one()

    items_result = await db.execute(
        select(Article)
        .where(Article.search_run_id == run_id)
        .order_by(Article.created_at)
        .offset(offset)
        .limit(page_size)
    )
    items = list(items_result.scalars().all())

    return ArticleListOut(
        items=[ArticleOut.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/ws/{project_id}")
async def websocket_search_progress(
    project_id: str,
    ws: WebSocket,
    manager: WS,
) -> None:
    await manager.connect(project_id, ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive; server pushes events
    except WebSocketDisconnect:
        manager.disconnect(project_id, ws)
