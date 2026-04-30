"""Dedup service tests — strategy selection and within-batch deduplication.

Comprehensive DOI/PMID/fuzzy/log-row tests are in test_dedup.py.
This file covers: within-batch preference and the abstract-presence no-overwrite case.
"""

import uuid

from db.models import Article
from services.dedup import deduplicate
from services.parsers import ParsedArticle


async def _insert(db, project_id: str, **kwargs) -> Article:
    a = Article(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source="upload",
        authors=[],
        **kwargs,
    )
    db.add(a)
    await db.commit()
    return a


async def test_dedup_by_doi_removes_duplicate(db, project_id):
    """Second article with same DOI is a duplicate; only one is kept."""
    await _insert(db, project_id, title="Article A", doi="10.1234/test")
    incoming = [ParsedArticle(title="Article A duplicate", doi="10.1234/test")]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.new_articles) == 0
    assert len(result.duplicates) == 1
    assert result.duplicates[0][1] == "doi"


async def test_dedup_by_pmid_removes_duplicate(db, project_id):
    """Second article with same PMID is a duplicate."""
    await _insert(db, project_id, title="A", pmid="31009449")
    incoming = [ParsedArticle(title="A copy", pmid="31009449")]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.new_articles) == 0
    assert len(result.duplicates) == 1
    assert result.duplicates[0][1] == "pmid"


async def test_dedup_no_duplicates_unchanged(db, project_id):
    """Distinct articles are all kept as new."""
    incoming = [
        ParsedArticle(title="A", doi="10.1/a"),
        ParsedArticle(title="B", doi="10.2/b"),
    ]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.new_articles) == 2
    assert len(result.duplicates) == 0


async def test_dedup_existing_article_kept_over_incoming(db, project_id):
    """When an incoming article duplicates an existing DB article, the existing one is kept
    (kept_article_id points to the DB article, not the incoming one)."""
    existing = await _insert(db, project_id, title="Original", doi="10.1/same", abstract=None)
    incoming = [ParsedArticle(title="Incoming duplicate", doi="10.1/same")]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.new_articles) == 0
    assert result.duplicate_article_ids == [existing.id]
