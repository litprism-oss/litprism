import pytest

pytestmark = pytest.mark.integration

KNOWN_PMID = "15838583"  # Peluso MA — physical activity and mental health
KNOWN_ABSTRACT_FRAGMENT = "physical activity"


async def test_enrich_by_pmid_real(db):
    """Real PubMed fetch for a known PMID should return abstract."""
    from config import Settings
    from db.models import Article
    from services.enrichment import _enrich_by_pmid

    article = Article(
        id="integration-test-art-1",
        project_id="integration-test-proj",
        pmid=KNOWN_PMID,
        title="Physical activity and mental health",
        abstract=None,
        enrichment_status="pending",
        source="upload",
    )
    db.add(article)
    await db.commit()

    enriched = await _enrich_by_pmid([article], db, Settings())

    assert enriched == 1
    assert article.abstract is not None
    assert KNOWN_ABSTRACT_FRAGMENT.lower() in article.abstract.lower()
    assert article.enrichment_status == "enriched"


async def test_enrich_by_doi_real(db):
    """Real Europe PMC fetch for a known DOI."""
    from db.models import Article
    from services.enrichment import _enrich_by_doi

    article = Article(
        id="integration-test-art-2",
        project_id="integration-test-proj",
        pmid=None,
        doi="10.1590/s1807-59322005000100012",
        title="Physical activity and mental health",
        abstract=None,
        enrichment_status="pending",
        source="upload",
    )
    db.add(article)
    await db.commit()

    enriched = await _enrich_by_doi([article], db)

    assert enriched == 1
    assert article.abstract is not None
