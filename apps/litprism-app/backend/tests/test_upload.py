import io


async def test_upload_ris_file(client, project_id):
    content = b"TY  - JOUR\nTI  - Test Article\nER  -\n"
    resp = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("test.ris", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total_parsed"] == 1
    assert data["new_articles"] == 1
    assert data["duplicates_found"] == 0
    assert data["project_id"] == project_id
    assert data["filename"] == "test.ris"
    assert data["format"] == "ris"


async def test_upload_nbib_file(client, project_id):
    content = (
        b"PMID- 99999999\nTI  - An NBIB Article\nAB  - Some abstract.\nAU  - Smith, John\nER  -\n"
    )
    resp = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("test.nbib", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total_parsed"] == 1
    assert data["new_articles"] == 1


async def test_upload_unsupported_extension(client, project_id):
    resp = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("test.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert resp.status_code == 422


async def test_upload_deduplicates(client, project_id):
    content = b"TY  - JOUR\nTI  - Test Article\nDO  - 10.1234/test\nER  -\n"
    # First upload
    resp1 = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("a.ris", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp1.status_code == 201
    assert resp1.json()["new_articles"] == 1

    # Second upload of same file — should be deduplicated
    resp2 = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("b.ris", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp2.status_code == 201
    data = resp2.json()
    assert data["duplicates_found"] == 1
    assert data["new_articles"] == 0


async def test_upload_project_not_found(client):
    content = b"TY  - JOUR\nTI  - Test\nER  -\n"
    resp = await client.post(
        "/projects/00000000-0000-0000-0000-000000000000/upload",
        files={"file": ("test.ris", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp.status_code == 404


async def test_upload_csv_file(client, project_id):
    content = b"Title,Abstract,DOI\nCSV Article,An abstract,10.5678/csv\n"
    resp = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("test.csv", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp.status_code == 201
    assert resp.json()["total_parsed"] == 1


async def test_list_uploads(client, project_id):
    content = b"TY  - JOUR\nTI  - Listed Article\nER  -\n"
    await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("listed.ris", io.BytesIO(content), "application/octet-stream")},
    )
    resp = await client.get(f"/projects/{project_id}/uploads")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 1
    assert records[0]["filename"] == "listed.ris"


async def test_list_uploads_project_not_found(client):
    resp = await client.get("/projects/00000000-0000-0000-0000-000000000000/uploads")
    assert resp.status_code == 404
