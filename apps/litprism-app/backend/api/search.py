import asyncio
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from config import settings
from db.engine import AsyncSessionLocal, get_db
from db.models import Article, Project, SearchRun, SourceQuery, UploadRecord
from dependencies import get_ws_manager
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from litprism.pubmed.parser import parse_xml
from services.pipeline import run_search
from services.query_translator import QueryTranslator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
from ws import ConnectionManager

from api.schemas import (
    ArticleListOut,
    ArticleOut,
    SearchPreviewRequest,
    SearchPreviewResponse,
    SearchPreviewSource,
    SearchRunCreate,
    SearchRunOut,
    SearchRunUpdate,
)

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
# Search preview helpers (stateless — no DB writes)
# ---------------------------------------------------------------------------

_PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"


async def _preview_pubmed(query: str, api_key: str | None) -> SearchPreviewSource:
    """esearch (count + PMIDs) then efetch (titles) — two calls."""
    try:
        base: dict[str, Any] = {"db": "pubmed", "retmode": "json"}
        if api_key:
            base["api_key"] = api_key

        async with httpx.AsyncClient() as client:
            r = await client.get(
                _PUBMED_ESEARCH,
                params={**base, "term": query, "retmax": 10},
                timeout=15.0,
            )
            r.raise_for_status()
            esearch = r.json().get("esearchresult", {})
            count = int(esearch.get("count", 0))
            pmids: list[str] = esearch.get("idlist", [])[:10]

            if not pmids:
                return SearchPreviewSource(source="pubmed", estimated_count=count, sample_titles=[])

            r2 = await client.get(
                _PUBMED_EFETCH,
                params={**base, "rettype": "xml", "retmode": "xml", "id": ",".join(pmids)},
                timeout=15.0,
            )
            r2.raise_for_status()

        articles = parse_xml(r2.text)
        return SearchPreviewSource(
            source="pubmed",
            estimated_count=count,
            sample_titles=[a.title for a in articles[:10]],
        )
    except httpx.HTTPStatusError as exc:
        msg = (
            "Rate limited — try again in a moment"
            if exc.response.status_code == 429
            else f"HTTP {exc.response.status_code}"
        )
        return SearchPreviewSource(source="pubmed", estimated_count=0, sample_titles=[], error=msg)
    except Exception as exc:
        return SearchPreviewSource(
            source="pubmed", estimated_count=0, sample_titles=[], error=str(exc)
        )


async def _preview_europepmc(query: str) -> SearchPreviewSource:
    """Single search call — hitCount + first 10 titles."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                _EUROPEPMC_SEARCH,
                params={
                    "query": query,
                    "pageSize": 10,
                    "cursorMark": "*",
                    "format": "json",
                    "resultType": "core",
                    "synonym": "true",
                },
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()

        count: int = data.get("hitCount", 0)
        results: list[dict[str, Any]] = data.get("resultList", {}).get("result", [])
        titles = [item.get("title") or "" for item in results]
        return SearchPreviewSource(source="europepmc", estimated_count=count, sample_titles=titles)
    except httpx.HTTPStatusError as exc:
        msg = (
            "Rate limited — try again in a moment"
            if exc.response.status_code == 429
            else f"HTTP {exc.response.status_code}"
        )
        return SearchPreviewSource(
            source="europepmc", estimated_count=0, sample_titles=[], error=msg
        )
    except Exception as exc:
        return SearchPreviewSource(
            source="europepmc", estimated_count=0, sample_titles=[], error=str(exc)
        )


def _is_s2_rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


@retry(
    retry=retry_if_exception(_is_s2_rate_limited),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _fetch_s2_preview(query: str, headers: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            _S2_SEARCH,
            params={"query": query, "fields": "title", "limit": 10, "offset": 0},
            headers=headers,
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()


async def _preview_semanticscholar(query: str, api_key: str | None) -> SearchPreviewSource:
    """Single search call with retry on 429 — total + first 10 titles."""
    try:
        headers: dict[str, str] = {}
        if api_key:
            headers["x-api-key"] = api_key

        data = await _fetch_s2_preview(query, headers)

        count = data.get("total", 0)
        results: list[dict[str, Any]] = data.get("data") or []
        titles = [p.get("title") or "" for p in results]
        return SearchPreviewSource(
            source="semanticscholar", estimated_count=count, sample_titles=titles
        )
    except httpx.HTTPStatusError as exc:
        msg = (
            "Rate limited — try again in a moment"
            if exc.response.status_code == 429
            else f"HTTP {exc.response.status_code}"
        )
        return SearchPreviewSource(
            source="semanticscholar", estimated_count=0, sample_titles=[], error=msg
        )
    except Exception as exc:
        return SearchPreviewSource(
            source="semanticscholar", estimated_count=0, sample_titles=[], error=str(exc)
        )


# ---------------------------------------------------------------------------
# Search preview endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/search-runs/preview",
    response_model=SearchPreviewResponse,
)
async def preview_search(
    project_id: str,
    body: SearchPreviewRequest,
    db: DB,
) -> SearchPreviewResponse:
    """Stateless search preview — no DB writes.

    Translates the query for each requested source, fetches a count and up to
    10 sample titles from each source concurrently, and returns the aggregated
    result.  Per-source errors are captured on SearchPreviewSource.error so a
    single failing source never fails the whole response.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    _translators = {
        "pubmed": QueryTranslator.to_pubmed,
        "europepmc": QueryTranslator.to_europepmc,
        "semanticscholar": QueryTranslator.to_semantic_scholar,
    }

    query_translations: dict[str, str] = {
        src: _translators[src](body.query_final) for src in body.sources if src in _translators
    }

    async def _task_for(source: str) -> SearchPreviewSource:
        translated = query_translations.get(source, body.query_final)
        if source == "pubmed":
            return await _preview_pubmed(translated, settings.pubmed_api_key or None)
        if source == "europepmc":
            return await _preview_europepmc(translated)
        if source == "semanticscholar":
            return await _preview_semanticscholar(
                translated, settings.semantic_scholar_api_key or None
            )
        return SearchPreviewSource(
            source=source, estimated_count=0, sample_titles=[], error=f"Unknown source: {source}"
        )

    source_results: list[SearchPreviewSource] = list(
        await asyncio.gather(*[_task_for(src) for src in body.sources])
    )

    total_estimated = sum(r.estimated_count for r in source_results if r.error is None)

    return SearchPreviewResponse(
        total_estimated=total_estimated,
        sources=source_results,
        query_translations=query_translations,
    )


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


@router.get("/projects/{project_id}/articles", response_model=ArticleListOut)
async def list_project_articles(
    project_id: str,
    db: DB,
    source_query_id: str | None = Query(None),
    upload_record_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ArticleListOut:
    filters = [Article.project_id == project_id]

    if source_query_id:
        sq_result = await db.execute(select(SourceQuery).where(SourceQuery.id == source_query_id))
        sq = sq_result.scalar_one_or_none()
        if sq is None:
            raise HTTPException(status_code=404, detail="Source query not found")
        filters.append(Article.search_run_id == sq.search_run_id)
        filters.append(Article.source == sq.source)
    elif upload_record_id:
        ur_result = await db.execute(
            select(UploadRecord).where(UploadRecord.id == upload_record_id)
        )
        ur = ur_result.scalar_one_or_none()
        if ur is None:
            raise HTTPException(status_code=404, detail="Upload record not found")
        filters.append(Article.search_run_id == ur.search_run_id)
        filters.append(Article.source == "upload")

    offset = (page - 1) * page_size
    total: int = (await db.execute(select(func.count(Article.id)).where(*filters))).scalar_one()
    items = list(
        (
            await db.execute(
                select(Article)
                .where(*filters)
                .order_by(Article.created_at)
                .offset(offset)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return ArticleListOut(
        items=[ArticleOut.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


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
