async def test_create_first_criteria_version(client, project_id):
    resp = await client.post(
        f"/projects/{project_id}/criteria",
        json={
            "inclusion": ["RCT"],
            "exclusion": ["Animal study"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 1
    assert data["superseded_at"] is None


async def test_create_second_version_supersedes_first(client, project_id):
    await client.post(
        f"/projects/{project_id}/criteria",
        json={
            "inclusion": ["RCT"],
            "exclusion": ["Animal study"],
        },
    )
    resp = await client.post(
        f"/projects/{project_id}/criteria",
        json={
            "inclusion": ["RCT", "Adults ≥18"],
            "exclusion": ["Animal study"],
        },
    )
    assert resp.json()["version"] == 2
    history = await client.get(f"/projects/{project_id}/criteria/history")
    items = history.json()
    assert len(items) == 2
    assert items[0]["superseded_at"] is not None  # v1 superseded
    assert items[1]["superseded_at"] is None  # v2 active


async def test_get_active_criteria(client, project_id, criteria_id):
    resp = await client.get(f"/projects/{project_id}/criteria")
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


async def test_get_criteria_history_ordered(client, project_id):
    for _ in range(3):
        await client.post(
            f"/projects/{project_id}/criteria",
            json={
                "inclusion": ["RCT"],
                "exclusion": [],
            },
        )
    resp = await client.get(f"/projects/{project_id}/criteria/history")
    versions = [c["version"] for c in resp.json()]
    assert versions == sorted(versions)


async def test_get_criteria_by_version(client, project_id, criteria_id):
    resp = await client.get(f"/projects/{project_id}/criteria/1")
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


async def test_stale_count_zero_when_no_results(client, project_id, criteria_id):
    resp = await client.get(f"/projects/{project_id}/screening/stale-count")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stale_results"] == 0
    assert data["active_criteria_version"] == 1


async def test_empty_inclusion_rejected(client, project_id):
    resp = await client.post(
        f"/projects/{project_id}/criteria",
        json={
            "inclusion": [],
            "exclusion": ["Animal study"],
        },
    )
    assert resp.status_code == 422


async def test_blank_criterion_rejected(client, project_id):
    resp = await client.post(
        f"/projects/{project_id}/criteria",
        json={
            "inclusion": ["  "],
            "exclusion": [],
        },
    )
    assert resp.status_code == 422
