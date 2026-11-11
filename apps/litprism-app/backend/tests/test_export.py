import io
import json
import zipfile


async def test_export_ris(client, project_id, articles_in_db):
    resp = await client.get(f"/projects/{project_id}/export/ris")
    assert resp.status_code == 200
    assert "application/x-research-info-systems" in resp.headers["content-type"]
    assert b"TY  -" in resp.content


async def test_export_nbib(client, project_id, articles_in_db):
    resp = await client.get(f"/projects/{project_id}/export/nbib")
    assert resp.status_code == 200
    assert b"TI  -" in resp.content


async def test_export_csv(client, project_id, articles_in_db):
    resp = await client.get(f"/projects/{project_id}/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert b"Title" in resp.content


async def test_export_json(client, project_id, articles_in_db):
    resp = await client.get(f"/projects/{project_id}/export/json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    data = json.loads(resp.content)
    assert isinstance(data, list)
    assert len(data) == 5
    assert all("title" in item for item in data)


async def test_export_asreview(client, project_id, articles_with_decisions):
    resp = await client.get(f"/projects/{project_id}/export/asreview")
    assert resp.status_code == 200
    assert "zip" in resp.headers["content-type"]
    # Verify ZIP contains expected files
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "data.csv" in names
    assert "metadata.json" in names
    meta = json.loads(zf.read("metadata.json"))
    assert meta["software"] == "LitPrism"


async def test_export_prisma_s(client, project_id, search_run_with_source_queries):
    resp = await client.get(f"/projects/{project_id}/export/prisma-s")
    assert resp.status_code == 200
    assert "wordprocessingml" in resp.headers["content-type"]
    assert len(resp.content) > 0


async def test_export_filter_by_decision(client, project_id, articles_with_decisions):
    resp = await client.get(f"/projects/{project_id}/export/ris?decision=include")
    assert resp.status_code == 200
    # 3 of 5 articles are "include" in the fixture
    content = resp.content.decode("utf-8")
    # Count TY  - JOUR occurrences — one per article
    assert content.count("TY  -") == 3


async def test_export_invalid_format(client, project_id):
    resp = await client.get(f"/projects/{project_id}/export/docx")
    assert resp.status_code == 422


async def test_export_project_not_found(client):
    resp = await client.get("/projects/00000000-0000-0000-0000-000000000000/export/ris")
    assert resp.status_code == 404


async def test_export_empty_project(client, project_id):
    """Export with no articles should return an empty but valid file."""
    resp = await client.get(f"/projects/{project_id}/export/json")
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data == []
