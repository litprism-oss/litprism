async def test_create_project(client):
    resp = await client.post("/projects", json={"name": "My Review", "review_type": "systematic"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Review"
    assert data["review_type"] == "systematic"
    assert "id" in data


async def test_list_projects_empty(client):
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_project_not_found(client):
    resp = await client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_project(client, project_id):
    resp = await client.patch(f"/projects/{project_id}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


async def test_delete_project(client, project_id):
    resp = await client.delete(f"/projects/{project_id}")
    assert resp.status_code == 204
    get = await client.get(f"/projects/{project_id}")
    assert get.status_code == 404


async def test_project_stats_reflect_articles_and_screening(client, db, project_id):
    from datetime import UTC, datetime

    from db.models import Article, Criteria, ScreeningResult

    now = datetime.now(UTC)
    crit = Criteria(
        id="c1", project_id=project_id, version=1, inclusion=["a"], exclusion=[], created_at=now
    )
    db.add(crit)
    for i, (d, human) in enumerate([("include", None), ("exclude", "include"), ("exclude", None)]):
        db.add(Article(id=f"a{i}", project_id=project_id, title=f"t{i}", source="upload"))
        db.add(
            ScreeningResult(
                id=f"r{i}",
                article_id=f"a{i}",
                project_id=project_id,
                criteria_id="c1",
                stage="abstract",
                decision=d,
                human_decision=human,
                confidence=0.9,
                reasoning="x",
                criteria_hits=[],
                model_used="m",
                llm_provider="p",
                screened_at=now,
            )
        )
    await db.commit()

    body = (await client.get(f"/projects/{project_id}")).json()
    assert body["article_count"] == 3
    assert body["screened_count"] == 3
    assert body["included_count"] == 2  # one model include + one human override to include
    assert body["has_criteria"] is True
    listed = (await client.get("/projects")).json()
    assert next(p for p in listed if p["id"] == project_id)["article_count"] == 3


async def test_delete_project_removes_children_in_database(client, db, project_id):
    from datetime import UTC, datetime

    from db.models import Article, Criteria, Project, ScreeningResult
    from sqlalchemy import func, select

    now = datetime.now(UTC)
    db.add(
        Criteria(
            id="dc", project_id=project_id, version=1, inclusion=["a"], exclusion=[], created_at=now
        )
    )
    db.add(Article(id="da", project_id=project_id, title="t", source="upload"))
    await db.flush()
    db.add(
        ScreeningResult(
            id="dr",
            article_id="da",
            project_id=project_id,
            criteria_id="dc",
            stage="abstract",
            decision="include",
            confidence=0.9,
            reasoning="x",
            criteria_hits=[],
            model_used="m",
            llm_provider="p",
            screened_at=now,
        )
    )
    await db.commit()

    assert (await client.delete(f"/projects/{project_id}")).status_code == 204
    db.expire_all()
    for model in (Project, Article, Criteria, ScreeningResult):
        assert (await db.execute(select(func.count()).select_from(model))).scalar() == 0
