import pytest

pytestmark = pytest.mark.integration


async def test_prisma_s_docx_downloads(client):
    """PRISMA-S endpoint should return a valid .docx file."""
    projects = (await client.get("/projects")).json()
    project_id = projects[0]["id"] if projects else None
    if not project_id:
        pytest.skip("No project available")

    response = await client.get(f"/projects/{project_id}/export/prisma-s")
    assert response.status_code == 200
    assert "wordprocessingml" in response.headers.get("content-type", "")
    assert len(response.content) > 1000  # non-empty document

    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(response.content))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "PRISMA-S" in full_text


async def test_ris_export_real(client):
    """RIS export should contain TY and TI fields."""
    projects = (await client.get("/projects")).json()
    project_id = projects[0]["id"] if projects else None
    if not project_id:
        pytest.skip("No project available")

    response = await client.get(f"/projects/{project_id}/export/ris")
    assert response.status_code == 200
    content = response.text
    assert "TY  -" in content
    assert "TI  -" in content


async def test_csv_export_real(client):
    """CSV export should have correct headers."""
    projects = (await client.get("/projects")).json()
    project_id = projects[0]["id"] if projects else None
    if not project_id:
        pytest.skip("No project available")

    response = await client.get(f"/projects/{project_id}/export/csv")
    assert response.status_code == 200
    first_line = response.text.split("\n")[0].lower()
    assert "title" in first_line
    assert "doi" in first_line
