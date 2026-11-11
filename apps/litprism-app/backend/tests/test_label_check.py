"""Label check: compare AI decisions with a reviewer's CSV labels."""

import uuid
from datetime import UTC, datetime

import pytest
from db.models import Article, Criteria, ScreeningResult, ScreeningRun
from services.label_check import compare, parse_labels


def test_parse_labels_accepts_asreview_columns_and_doi():
    rows = parse_labels(b"Title,DOI,label_included\nA study,https://doi.org/10.1/X,1\nOther,,0\n")
    assert [(r.title, r.doi, r.label) for r in rows] == [
        ("A study", "10.1/x", True),
        ("Other", None, False),
    ]


def test_parse_labels_rejects_missing_label_column():
    with pytest.raises(ValueError, match="label column"):
        parse_labels(b"title,abstract\nA,b\n")


def test_compare_counts_missed_relevant_and_unmatched():
    arts = [
        ("1", "Alpha trial", None, "include"),
        ("2", "Beta study", "10.5/b", "exclude"),
        ("3", "Gamma note", None, "exclude"),
    ]
    rows = parse_labels(
        b"title,doi,label\nalpha  TRIAL,,1\nwrong title,10.5/B,1\nGamma note,,0\nNot here,,1\n"
    )
    r = compare(rows, arts)
    assert (r.matched, r.unmatched, r.missed_total) == (3, 1, 1)
    assert r.missed_titles == ["Beta study"]
    assert r.metrics is not None
    assert r.metrics.recall == 0.5 and r.metrics.work_saved == pytest.approx(2 / 3)


async def _seed(client, project_id, db):
    crit = Criteria(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version=1,
        inclusion=["x"],
        exclusion=[],
        uncertain_threshold=0.9,
        created_at=datetime.now(UTC),
    )
    db.add(crit)
    run = ScreeningRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        criteria_id=crit.id,
        stage="abstract",
        status="completed",
        total_articles=2,
        created_at=datetime.now(UTC),
    )
    db.add(run)
    for title, dec in (("Alpha trial", "include"), ("Beta study", "exclude")):
        a = Article(
            id=str(uuid.uuid4()), project_id=project_id, title=title, source="upload", authors=[]
        )
        db.add(a)
        await db.flush()
        db.add(
            ScreeningResult(
                id=str(uuid.uuid4()),
                article_id=a.id,
                project_id=project_id,
                criteria_id=crit.id,
                screening_run_id=run.id,
                stage="abstract",
                decision=dec,
                confidence=0.9,
                reasoning="r",
                criteria_hits=[],
                model_used="m",
                llm_provider="p",
                screened_at=datetime.now(UTC),
            )
        )
    await db.commit()


async def test_label_check_endpoint(client, project_id, db):
    await _seed(client, project_id, db)
    csv_bytes = b"title,label\nAlpha trial,1\nBeta study,1\n"
    resp = await client.post(
        f"/projects/{project_id}/screening/label-check",
        files={"file": ("labels.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched"] == 2 and body["relevant"] == 2
    assert body["recall"] == 0.5 and body["missed"] == 1
    assert body["missed_titles"] == ["Beta study"]


async def test_label_check_needs_screened_articles(client, project_id):
    resp = await client.post(
        f"/projects/{project_id}/screening/label-check",
        files={"file": ("l.csv", b"title,label\nA,1\n", "text/csv")},
    )
    assert resp.status_code == 409


async def test_label_check_bad_file(client, project_id, db):
    await _seed(client, project_id, db)
    resp = await client.post(
        f"/projects/{project_id}/screening/label-check",
        files={"file": ("l.csv", b"foo,bar\n1,2\n", "text/csv")},
    )
    assert resp.status_code == 422
