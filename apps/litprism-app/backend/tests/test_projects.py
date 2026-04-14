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
