import pytest_asyncio
from db.engine import get_db
from db.models import Base
from httpx import ASGITransport, AsyncClient
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
