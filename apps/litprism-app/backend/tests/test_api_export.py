"""Export API tests — format-specific content, decision filter, empty project."""

import json


async def test_export_ris_contains_title_tag(client, project_id, articles_in_db):
    """RIS export should have TY and TI tags for each article."""
    resp = await client.get(f"/projects/{project_id}/export/ris")
    assert resp.status_code == 200
    content = resp.text
    assert "TY  -" in content
    assert "TI  -" in content


async def test_export_csv_has_doi_column(client, project_id, articles_in_db):
    """CSV export first row must include title and doi columns."""
    resp = await client.get(f"/projects/{project_id}/export/csv")
    assert resp.status_code == 200
    first_line = resp.text.split("\n")[0].lower()
    assert "title" in first_line
    assert "doi" in first_line


async def test_export_json_returns_article_list(client, project_id, articles_in_db):
    """JSON export should be a list with all articles and required fields."""
    resp = await client.get(f"/projects/{project_id}/export/json")
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert isinstance(data, list)
    assert len(data) == 5
    assert all("title" in item and "doi" in item for item in data)
