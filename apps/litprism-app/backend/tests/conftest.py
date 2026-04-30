import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest_asyncio.fixture(scope="function")
async def db():
    """In-memory SQLite for tests — no real DB needed."""
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


@pytest_asyncio.fixture(scope="function")
async def client(db):
    """AsyncClient with ASGI transport, overrides get_db."""
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_project_id():
    return "test-project-123"


@pytest_asyncio.fixture
async def project_id(client):
    """Helper fixture to create a real project in the DB."""
    resp = await client.post(
        "/projects", json={"name": "Test Project", "review_type": "systematic"}
    )
    return resp.json()["id"]


@pytest_asyncio.fixture
async def criteria_id(client, project_id):
    """Helper fixture to create real criteria in the DB."""
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


@pytest.fixture(autouse=True)
def mock_enrich_task():
    """Auto-mock enrich_articles_task.delay — prevents Celery/Redis connection in all tests."""
    with patch("api.upload.enrich_articles_task") as m:
        m.delay = MagicMock()
        yield m


@pytest.fixture(autouse=True)
def mock_run_search_task():
    """Auto-mock _run_search_task — prevents it opening AsyncSessionLocal (real DB) in tests."""

    async def _noop(*args, **kwargs):
        pass

    with patch("api.search._run_search_task", side_effect=_noop):
        yield


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
async def articles_in_db(db, project_id):
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
        db.add(a)
        articles.append(a)
    await db.commit()
    return articles


@pytest_asyncio.fixture
async def articles_with_decisions(db, project_id):
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
    db.add(criteria)

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
        db.add(a)
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
        db.add(sr)
        articles.append(a)

    await db.commit()
    return articles


@pytest_asyncio.fixture
async def search_run_with_source_queries(db, project_id):
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
    db.add(run)

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
        db.add(sq)

    await db.commit()
    return run


# ---------------------------------------------------------------------------
# Session 12 — file fixtures for parser and upload tests
# ---------------------------------------------------------------------------


@pytest.fixture
def pubmed_csv_path(tmp_path):
    """PubMed CSV export with BOM — the format that was broken."""
    content = (
        "\ufeffPMID,Title,Authors,Journal/Book,Publication Year,DOI\n"
        "31009449,Probiotic therapy in Crohn's disease,Smith J,J Nutr,2024,10.1234/test\n"
        "29256392,Gut microbiome in colitis,Jones A,Nutrients,2023,\n"
    )
    p = tmp_path / "pubmed_export.csv"
    p.write_text(content, encoding="utf-8")
    return str(p)


@pytest.fixture
def scopus_ris_path(tmp_path):
    """Scopus RIS export — DOI present, no PMID."""
    content = (
        "TY  - JOUR\n"
        "TI  - Iron bioavailability from fortified wheat\n"
        "AU  - Smith, John\n"
        "AU  - Jones, Alice\n"
        "PY  - 2023\n"
        "DO  - 10.1016/j.clnesp.2020.09.027\n"
        "JO  - Clinical Nutrition ESPEN\n"
        "AB  - Background: Iron deficiency affects 2 billion people worldwide...\n"
        "ER  -\n"
    )
    p = tmp_path / "scopus_export.ris"
    p.write_text(content)
    return str(p)


@pytest.fixture
def pubmed_nbib_path(tmp_path):
    """PubMed NBIB export — includes abstract."""
    content = (
        "PMID- 31009449\n"
        "TI  - Probiotic therapy in Crohn's disease\n"
        "AB  - Background: Probiotics have shown promise...\n"
        "FAU - Smith, John Andrew\n"
        "AU  - Smith JA\n"
        "TA  - J Nutr\n"
        "DP  - 2024 Feb\n"
        "AID - 10.1234/test [doi]\n"
        "\n"
    )
    p = tmp_path / "pubmed.nbib"
    p.write_text(content)
    return str(p)


@pytest.fixture
def pubmed_summary_txt_path(tmp_path):
    """PubMed Summary .txt — positional parsing."""
    content = (
        "1: Smith JA, Jones AB. Probiotic therapy in Crohn's disease. "
        "J Nutr. 2024 Feb;24(1):61-70. doi: 10.1234/test. PMID: 31009449.\n"
        "\n"
        "2: Jones AB. Gut microbiome in murine colitis. "
        "Nutrients. 2023 Jul;15(7):1234. doi: 10.5678/test2. PMID: 29256392.\n"
    )
    p = tmp_path / "pubmed_summary.txt"
    p.write_text(content)
    return str(p)


@pytest.fixture
def pubmed_medline_txt_path(tmp_path):
    """PubMed MEDLINE .txt — tagged format, starts with PMID-."""
    content = (
        "PMID- 31009449\n"
        "TI  - Probiotic therapy in Crohn's disease\n"
        "AB  - Background: Probiotics have shown promise...\n"
        "FAU - Smith, John\n"
        "DP  - 2024 Feb\n"
        "\n"
    )
    p = tmp_path / "pubmed_medline.txt"
    p.write_text(content)
    return str(p)
