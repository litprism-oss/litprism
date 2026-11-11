import asyncio
import logging
from difflib import SequenceMatcher

from config import Settings
from db.models import Article
from litprism.europepmc import AsyncEuropePMCClient
from litprism.pubmed import AsyncPubMedClient
from litprism.semanticscholar import AsyncSemanticScholarClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PUBMED_BATCH_SIZE = 200
EUROPEPMC_BATCH_SIZE = 50


async def enrich_articles(
    project_id: str,
    article_ids: list[str],
    db: AsyncSession,
    settings: Settings,
) -> dict[str, int]:
    """Enrich articles with missing abstracts. Returns counts."""
    articles = await _load_unenriched(article_ids, db)

    counts = {"enriched": 0, "not_found": 0, "skipped": 0, "errors": 0}

    has_abstract = [a for a in articles if a.abstract and a.abstract.strip()]
    by_pmid = [a for a in articles if not (a.abstract and a.abstract.strip()) and a.pmid]
    by_doi = [
        a for a in articles if not (a.abstract and a.abstract.strip()) and not a.pmid and a.doi
    ]
    by_title = [
        a
        for a in articles
        if not (a.abstract and a.abstract.strip()) and not a.pmid and not a.doi and a.title
    ]

    for article in has_abstract:
        article.enrichment_status = "skipped"
        counts["skipped"] += 1

    if by_pmid:
        counts["enriched"] += await _enrich_by_pmid(by_pmid, db, settings)

    if by_doi:
        counts["enriched"] += await _enrich_by_doi(by_doi, db)

    if by_title:
        counts["enriched"] += await _enrich_by_title(by_title, db, settings)

    for article in articles:
        still_missing = not (article.abstract and article.abstract.strip())
        if still_missing and article.enrichment_status == "pending":
            article.enrichment_status = "not_found"
            counts["not_found"] += 1

    await db.commit()
    logger.info("Enrichment complete project=%s %s", project_id, counts)
    return counts


async def _load_unenriched(article_ids: list[str], db: AsyncSession) -> list[Article]:
    result = await db.execute(select(Article).where(Article.id.in_(article_ids)))
    articles = list(result.scalars().all())
    for a in articles:
        if not (a.abstract and a.abstract.strip()):
            a.enrichment_status = "pending"
    await db.commit()
    return articles


async def _enrich_by_pmid(
    articles: list[Article],
    db: AsyncSession,
    settings: Settings,
) -> int:
    enriched = 0
    client = AsyncPubMedClient(api_key=settings.pubmed_api_key or None)

    for i in range(0, len(articles), PUBMED_BATCH_SIZE):
        batch = articles[i : i + PUBMED_BATCH_SIZE]
        pmids = [a.pmid for a in batch]

        try:
            fetched = await client.fetch(pmids)
            fetched_map = {f.pmid: f for f in fetched if f.pmid}

            for article in batch:
                hit = fetched_map.get(article.pmid)
                if hit and hit.abstract:
                    article.abstract = hit.abstract
                    article.enrichment_status = "enriched"
                    if not article.authors and hit.authors:
                        article.authors = [a.model_dump() for a in hit.authors]
                    enriched += 1

        except Exception as e:
            logger.warning("PubMed enrichment batch failed: %s", e)

        await asyncio.sleep(0.1)

    return enriched


async def _enrich_by_doi(articles: list[Article], db: AsyncSession) -> int:
    enriched = 0
    client = AsyncEuropePMCClient()

    for article in articles:
        try:
            results = await client.search(query=f'DOI:"{article.doi}"', max_results=1)
            if results and results[0].abstract:
                article.abstract = results[0].abstract
                article.enrichment_status = "enriched"
                enriched += 1

        except Exception as e:
            logger.warning("EuropePMC DOI enrichment failed doi=%s: %s", article.doi, e)

        await asyncio.sleep(0.05)

    return enriched


async def _enrich_by_title(
    articles: list[Article],
    db: AsyncSession,
    settings: Settings,
) -> int:
    enriched = 0
    client = AsyncSemanticScholarClient(api_key=settings.semantic_scholar_api_key or None)

    for article in articles:
        if not article.title:
            continue
        try:
            results = await client.search(query=article.title, max_results=1)
            if not results:
                continue

            similarity = SequenceMatcher(
                None,
                article.title.lower(),
                results[0].title.lower(),
            ).ratio()

            if similarity > 0.95 and results[0].abstract:
                article.abstract = results[0].abstract
                article.enrichment_status = "enriched"
                enriched += 1

        except Exception as e:
            logger.warning("S2 title enrichment failed title=%s: %s", article.title[:50], e)

        await asyncio.sleep(0.1)

    return enriched
