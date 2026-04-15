from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from db.engine import get_db
from db.models import Base
from httpx import ASGITransport, AsyncClient
from litprism.pubmed.models import Article as PubMedArticle
from litprism.screen.models import ScreeningResult
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def project_id(client):
    resp = await client.post(
        "/projects", json={"name": "Test Project", "review_type": "systematic"}
    )
    return resp.json()["id"]


@pytest_asyncio.fixture
async def criteria_id(client, project_id):
    resp = await client.post(
        f"/projects/{project_id}/criteria",
        json={
            "inclusion": ["RCT or quasi-RCT", "Adult participants ≥18"],
            "exclusion": ["Animal study"],
        },
    )
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Session 7.2 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_articles():
    """Three minimal PubMedArticle objects for mocking search results."""
    return [PubMedArticle(id=f"pmid_{i}", title=f"Article {i}", source="pubmed") for i in range(3)]


@pytest.fixture
def mock_pubmed_client(fake_articles):
    """AsyncPubMedClient whose search_iter yields one batch of 3 articles."""

    async def _iter(*args, **kwargs):
        yield fake_articles

    client = AsyncMock()
    client.search_iter = _iter
    return client


@pytest.fixture
def mock_pipeline():
    """Patches run_search to do nothing — prevents real HTTP calls in route tests."""
    with patch("api.search.run_search", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_screener():
    """Patches Screener.from_env to return an AsyncMock screener."""
    fake_result = ScreeningResult(
        article_id="temp_1",
        decision="include",
        confidence=0.95,
        reasoning="Clearly meets all criteria.",
        criteria_hits=[],
        stage="abstract",
        model_used="gpt-5.4-mini",
        llm_provider="openai",
        screened_at=datetime.now(UTC),
    )

    async def _batch(articles, criteria, stage="abstract"):
        results = [
            ScreeningResult(**{**fake_result.model_dump(), "article_id": a.id}) for a in articles
        ]
        return results, []

    screener = AsyncMock()
    screener.ascreen_batch = _batch

    with patch("api.screening.Screener") as MockScreener:
        MockScreener.from_env.return_value = screener
        yield screener


@pytest.fixture
def mock_coordinator():
    """Patches screen_coordinator.delay to do nothing — prevents real Celery dispatch."""
    with patch("api.screening.screen_coordinator.delay") as m:
        yield m
