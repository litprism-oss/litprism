from db.models import Article
from sqlalchemy import func, select


async def test_preview_returns_results(client, project_id, mock_screener):
    resp = await client.post(
        f"/projects/{project_id}/screening/preview",
        json={
            "criteria": {"inclusion": ["RCT"], "exclusion": ["Animal"]},
            "articles": [{"id": "temp_1", "title": "A trial", "abstract": "Methods: RCT..."}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["article_id"] == "temp_1"
    assert data[0]["decision"] in ("include", "exclude", "uncertain")


async def test_preview_more_than_ten_articles_rejected(client, project_id):
    articles = [{"id": f"t{i}", "title": f"Article {i}"} for i in range(11)]
    resp = await client.post(
        f"/projects/{project_id}/screening/preview",
        json={
            "criteria": {"inclusion": ["RCT"], "exclusion": []},
            "articles": articles,
        },
    )
    assert resp.status_code == 422


async def test_preview_zero_articles_rejected(client, project_id):
    resp = await client.post(
        f"/projects/{project_id}/screening/preview",
        json={
            "criteria": {"inclusion": ["RCT"], "exclusion": []},
            "articles": [],
        },
    )
    assert resp.status_code == 422


async def test_preview_writes_nothing_to_db(client, project_id, mock_screener, db):
    before = (await db.execute(select(func.count(Article.id)))).scalar()
    await client.post(
        f"/projects/{project_id}/screening/preview",
        json={
            "criteria": {"inclusion": ["RCT"], "exclusion": []},
            "articles": [{"id": "t1", "title": "Test", "abstract": "RCT study"}],
        },
    )
    after = (await db.execute(select(func.count(Article.id)))).scalar()
    assert before == after


async def test_preview_project_not_found(client):
    resp = await client.post(
        "/projects/00000000-0000-0000-0000-000000000000/screening/preview",
        json={
            "criteria": {"inclusion": ["RCT"], "exclusion": []},
            "articles": [{"id": "t1", "title": "Test"}],
        },
    )
    assert resp.status_code == 404
