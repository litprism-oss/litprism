import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from db.models import Article, SearchRun, SourceQuery
from services.pipeline import run_search
from sqlalchemy import func, select
from ws import ConnectionManager


def _make_run(project_id: str) -> SearchRun:
    return SearchRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        review_type="systematic",
        query_final="test query",
        status="locked",
        locked_at=datetime.now(UTC),
    )


def _make_client_mock(fake_articles):
    """Return an object whose search_iter is an async generator yielding one batch."""

    class _MockClient:
        async def search_iter(self, *args, **kwargs):
            yield fake_articles

    return _MockClient()


@pytest.fixture
def ws_mock():
    manager = ConnectionManager()
    return manager


async def test_pipeline_writes_articles(db, project_id, fake_articles, ws_mock):
    run = _make_run(project_id)
    db.add(run)
    await db.commit()

    client_mock = _make_client_mock(fake_articles)

    with (
        patch("services.pipeline.AsyncPubMedClient", return_value=client_mock),
        patch("services.pipeline.EuropePMCClient", return_value=client_mock),
        patch("services.pipeline.SemanticScholarClient", return_value=client_mock),
    ):
        await run_search(project_id, run.id, db, ws_mock)

    count = (await db.execute(select(func.count(Article.id)))).scalar()
    # 3 sources × 3 articles each
    assert count == len(fake_articles) * 3


async def test_pipeline_writes_source_query(db, project_id, fake_articles, ws_mock):
    run = _make_run(project_id)
    db.add(run)
    await db.commit()

    client_mock = _make_client_mock(fake_articles)

    with (
        patch("services.pipeline.AsyncPubMedClient", return_value=client_mock),
        patch("services.pipeline.EuropePMCClient", return_value=client_mock),
        patch("services.pipeline.SemanticScholarClient", return_value=client_mock),
    ):
        await run_search(project_id, run.id, db, ws_mock)

    sq_count = (
        await db.execute(
            select(func.count(SourceQuery.id)).where(SourceQuery.search_run_id == run.id)
        )
    ).scalar()
    assert sq_count == 3  # one per source

    rows = (
        (await db.execute(select(SourceQuery).where(SourceQuery.search_run_id == run.id)))
        .scalars()
        .all()
    )
    sources = {r.source for r in rows}
    assert sources == {"pubmed", "europepmc", "semanticscholar"}
    for row in rows:
        assert row.result_count == len(fake_articles)


async def test_pipeline_sets_completed(db, project_id, fake_articles, ws_mock):
    run = _make_run(project_id)
    db.add(run)
    await db.commit()

    client_mock = _make_client_mock(fake_articles)

    with (
        patch("services.pipeline.AsyncPubMedClient", return_value=client_mock),
        patch("services.pipeline.EuropePMCClient", return_value=client_mock),
        patch("services.pipeline.SemanticScholarClient", return_value=client_mock),
    ):
        await run_search(project_id, run.id, db, ws_mock)

    await db.refresh(run)
    assert run.status == "completed"
    assert run.completed_at is not None


async def test_pipeline_sets_failed_on_exception(db, project_id, ws_mock):
    run = _make_run(project_id)
    db.add(run)
    await db.commit()

    class _BrokenClient:
        async def search_iter(self, *args, **kwargs):
            raise RuntimeError("simulated failure")
            yield  # make it a generator

    broken = _BrokenClient()

    with (
        patch("services.pipeline.AsyncPubMedClient", return_value=broken),
        patch("services.pipeline.EuropePMCClient", return_value=broken),
        patch("services.pipeline.SemanticScholarClient", return_value=broken),
        pytest.raises(RuntimeError, match="simulated failure"),
    ):
        await run_search(project_id, run.id, db, ws_mock)

    await db.refresh(run)
    assert run.status == "failed"
