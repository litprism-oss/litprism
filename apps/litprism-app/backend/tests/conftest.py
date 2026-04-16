import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from db.engine import get_db
from db.models import Article, Base, Criteria, ScreeningResult, SearchRun, SourceQuery
from httpx import ASGITransport, AsyncClient
from litprism.pubmed.models import Article as PubMedArticle
from litprism.screen import ScreeningResult as ScreenResult
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    fake_result = ScreenResult(
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
            ScreenResult(**{**fake_result.model_dump(), "article_id": a.id}) for a in articles
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


# ---------------------------------------------------------------------------
# Session 8 fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def articles_in_db(db_session, project_id):
    """Insert 5 articles directly into the DB for the project."""
    articles = []
    for i in range(5):
        a = Article(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=f"Test Article {i}",
            abstract=f"Abstract for article {i}.",
            authors=[{"last_name": f"Author{i}", "fore_name": "A"}],
            journal="Test Journal",
            source="upload",
            upload_format="ris",
            doi=f"10.1234/test.{i:04d}",
        )
        db_session.add(a)
        articles.append(a)
    await db_session.commit()
    return articles


@pytest_asyncio.fixture
async def articles_with_decisions(db_session, project_id):
    """Insert 5 articles + active criteria + screening_results (mix of decisions)."""
    # Create active criteria
    criteria = Criteria(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version=1,
        inclusion=["RCT or quasi-RCT"],
        exclusion=["Animal study"],
        uncertain_threshold=0.90,
        created_at=datetime.now(UTC),
    )
    db_session.add(criteria)

    decisions = ["include", "include", "exclude", "uncertain", "include"]
    articles = []
    for i, dec in enumerate(decisions):
        a = Article(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=f"Screened Article {i}",
            abstract=f"Abstract {i}.",
            authors=[{"last_name": f"Smith{i}", "fore_name": "J"}],
            source="upload",
            upload_format="ris",
            doi=f"10.9999/screened.{i:04d}",
        )
        db_session.add(a)
        sr = ScreeningResult(
            id=str(uuid.uuid4()),
            article_id=a.id,
            project_id=project_id,
            criteria_id=criteria.id,
            stage="abstract",
            decision=dec,
            confidence=0.95,
            reasoning="Meets criteria.",
            criteria_hits=[],
            model_used="test-model",
            llm_provider="openai",
            screened_at=datetime.now(UTC),
        )
        db_session.add(sr)
        articles.append(a)

    await db_session.commit()
    return articles


@pytest_asyncio.fixture
async def search_run_with_source_queries(db_session, project_id):
    """Insert a completed search_run + 2 source_query rows."""
    run = SearchRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        review_type="systematic",
        query_final='("probiotics"[tiab]) AND ("Crohn disease"[MeSH])',
        status="completed",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db_session.add(run)

    for source, interface in [("pubmed", "NCBI E-utilities"), ("europepmc", "REST API")]:
        sq = SourceQuery(
            id=str(uuid.uuid4()),
            search_run_id=run.id,
            source=source,
            interface=interface,
            query_string='("probiotics"[tiab]) AND ("Crohn disease"[MeSH])',
            filters_applied={"date_range": {"from": "2015", "to": "2024"}},
            filters_human_readable="Date: 2015–2024",
            searched_at=datetime.now(UTC),
            result_count=100,
        )
        db_session.add(sq)

    await db_session.commit()
    return run
