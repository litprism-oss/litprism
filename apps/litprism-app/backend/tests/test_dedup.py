import uuid

from db.models import Article
from services.dedup import DedupResult, _normalise_doi, _title_match, deduplicate
from services.parsers import ParsedArticle
from sqlalchemy import select

# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------


def test_normalise_doi_strips_https_prefix():
    assert _normalise_doi("https://doi.org/10.1234/test") == "10.1234/test"


def test_normalise_doi_strips_http_prefix():
    assert _normalise_doi("http://doi.org/10.1234/test") == "10.1234/test"


def test_normalise_doi_strips_doi_colon():
    assert _normalise_doi("doi:10.1234/test") == "10.1234/test"


def test_normalise_doi_lowercases():
    assert _normalise_doi("10.1234/TEST") == "10.1234/test"


def test_normalise_doi_none():
    assert _normalise_doi(None) is None


def test_normalise_doi_empty():
    assert _normalise_doi("") is None


def test_title_match_identical():
    assert _title_match("Effects of probiotics", "Effects of probiotics") == 100.0


def test_title_match_word_order():
    score = _title_match("probiotics and Crohn disease", "Crohn disease and probiotics")
    assert score >= 92


def test_title_match_different():
    score = _title_match("Quantum computing applications", "Effects of probiotics in Crohn disease")
    assert score < 92


def test_title_match_case_insensitive():
    score = _title_match("Effects of PROBIOTICS", "effects of probiotics")
    assert score == 100.0


# ---------------------------------------------------------------------------
# Async DB tests
# ---------------------------------------------------------------------------


async def _insert_article(db, project_id: str, **kwargs) -> Article:
    defaults = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "title": "Default Title",
        "source": "upload",
        "authors": [],
    }
    defaults.update(kwargs)
    a = Article(**defaults)
    db.add(a)
    await db.commit()
    return a


async def test_dedup_keeps_unmatched(db, project_id):
    incoming = [
        ParsedArticle(title="Probiotics for Crohn disease", doi="10.1111/unique.0001"),
        ParsedArticle(title="Quantum computing in drug discovery", doi="10.1111/unique.0002"),
        ParsedArticle(title="Machine learning for radiology imaging", doi="10.1111/unique.0003"),
    ]
    result = await deduplicate(incoming, project_id, db)
    assert isinstance(result, DedupResult)
    assert len(result.new_articles) == 3
    assert len(result.duplicates) == 0


async def test_dedup_removes_doi_match(db, project_id):
    await _insert_article(db, project_id, title="Existing Article", doi="10.1234/test")
    incoming = [ParsedArticle(title="Same Article Different Title", doi="10.1234/test")]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.new_articles) == 0
    assert len(result.duplicates) == 1
    assert result.duplicates[0][1] == "doi"


async def test_dedup_removes_pmid_match(db, project_id):
    await _insert_article(db, project_id, title="Existing Article", pmid="12345678")
    incoming = [ParsedArticle(title="Same Article", pmid="12345678")]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.new_articles) == 0
    assert len(result.duplicates) == 1
    assert result.duplicates[0][1] == "pmid"


async def test_dedup_fuzzy_title_match(db, project_id):
    await _insert_article(db, project_id, title="Effects of probiotics in Crohn disease")
    incoming = [ParsedArticle(title="Effects of Probiotics in Crohn's Disease")]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.new_articles) == 0
    assert len(result.duplicates) == 1
    assert result.duplicates[0][1] == "title_fuzzy"
    assert result.duplicates[0][2] >= 92


async def test_dedup_within_batch_doi(db, project_id):
    incoming = [
        ParsedArticle(title="Article A", doi="10.1234/same"),
        ParsedArticle(title="Article B", doi="10.1234/same"),
    ]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.new_articles) == 1
    assert len(result.duplicates) == 1
    assert result.duplicates[0][1] == "doi"


async def test_dedup_normalises_doi_before_matching(db, project_id):
    await _insert_article(db, project_id, title="Existing", doi="10.1234/test")
    # Incoming uses full URL prefix — should still be detected as duplicate
    incoming = [ParsedArticle(title="Same Paper", doi="https://doi.org/10.1234/test")]
    result = await deduplicate(incoming, project_id, db)
    assert len(result.duplicates) == 1


async def test_dedup_writes_log_row(db, project_id):
    existing = await _insert_article(
        db, project_id, title="Logged Article", doi="10.1234/logged"
    )
    incoming = [ParsedArticle(title="Duplicate", doi="10.1234/logged")]
    await deduplicate(incoming, project_id, db)
    await db.commit()

    from db.models import DeduplicationLog

    log_result = await db.execute(
        select(DeduplicationLog).where(DeduplicationLog.project_id == project_id)
    )
    logs = log_result.scalars().all()
    assert len(logs) == 1
    assert logs[0].kept_article_id == existing.id
    assert logs[0].duplicate_title == "Duplicate"
    assert logs[0].match_type == "doi"
