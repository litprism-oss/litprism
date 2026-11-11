async def test_create_search_run(client, project_id):
    resp = await client.post(
        f"/projects/{project_id}/search-runs",
        json={
            "review_type": "systematic",
            "query_final": '"Crohn disease"[MeSH] AND probiotic*[tiab]',
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"


async def test_update_draft_search_run(client, project_id):
    create = await client.post(
        f"/projects/{project_id}/search-runs",
        json={"review_type": "systematic"},
    )
    run_id = create.json()["id"]
    resp = await client.patch(
        f"/projects/{project_id}/search-runs/{run_id}",
        json={"query_final": "new query"},
    )
    assert resp.status_code == 200
    assert resp.json()["query_final"] == "new query"


async def test_cannot_update_locked_search_run(client, project_id, mock_pipeline):
    create = await client.post(
        f"/projects/{project_id}/search-runs",
        json={"review_type": "systematic"},
    )
    run_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/search-runs/{run_id}/execute")
    resp = await client.patch(
        f"/projects/{project_id}/search-runs/{run_id}",
        json={"query_final": "too late"},
    )
    assert resp.status_code == 409


async def test_execute_locks_search_run(client, project_id, mock_pipeline):
    create = await client.post(
        f"/projects/{project_id}/search-runs",
        json={"review_type": "systematic"},
    )
    run_id = create.json()["id"]
    resp = await client.post(f"/projects/{project_id}/search-runs/{run_id}/execute")
    assert resp.status_code == 202
    get = await client.get(f"/projects/{project_id}/search-runs/{run_id}")
    assert get.json()["status"] == "locked"
    assert get.json()["locked_at"] is not None
