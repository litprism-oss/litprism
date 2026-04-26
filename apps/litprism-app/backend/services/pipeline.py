import uuid
from datetime import UTC, datetime

from config import settings
from constants import ALL_SOURCES
from db.models import Article, SearchRun, SourceQuery
from litprism.europepmc import EuropePMCClient
from litprism.europepmc.models import SearchFilters as EuropePMCFilters
from litprism.pubmed import AsyncPubMedClient
from litprism.pubmed.filters import humanise_filters
from litprism.pubmed.models import SearchFilters as PubMedFilters
from litprism.semanticscholar import SemanticScholarClient
from litprism.semanticscholar.models import SearchFilters as S2Filters
from sqlalchemy.ext.asyncio import AsyncSession
from ws import ConnectionManager

from services.filter_translator import translate_for_source
from services.query_translator import QueryTranslator

BATCH_SIZES = {"pubmed": 200, "europepmc": 1000, "semanticscholar": 100}
SOURCE_INTERFACES = {
    "pubmed": "NCBI E-utilities",
    "europepmc": "EBI REST API",
    "semanticscholar": "S2 Academic API",
}

# SearchFilters model per source (same schema, different Literal on source field)
_FILTERS_MODEL = {
    "pubmed": PubMedFilters,
    "europepmc": EuropePMCFilters,
    "semanticscholar": S2Filters,
}


def _build_filters(filters_dict: dict | None, source: str):
    """Deserialise stored filters dict into the source SearchFilters object, or None."""
    if not filters_dict:
        return None
    try:
        return _FILTERS_MODEL[source](**filters_dict)
    except Exception:
        return None


async def run_search(
    project_id: str,
    search_run_id: str,
    db: AsyncSession,
    ws_manager: ConnectionManager,
) -> None:
    """
    Execute all source queries for a search run and persist results.
    Called via BackgroundTasks — must not block the event loop.
    """
    search_run = await db.get(SearchRun, search_run_id)
    if search_run is None or search_run.status != "locked":
        return

    clients = {
        "pubmed": AsyncPubMedClient(api_key=settings.pubmed_api_key or None),
        "europepmc": EuropePMCClient(),
        "semanticscholar": SemanticScholarClient(api_key=settings.semantic_scholar_api_key or None),
    }

    try:
        for source in search_run.sources or ALL_SOURCES:
            # Translate query to source syntax
            translator = {
                "pubmed": QueryTranslator.to_pubmed,
                "europepmc": QueryTranslator.to_europepmc,
                "semanticscholar": QueryTranslator.to_semantic_scholar,
            }[source]
            query_string = translator(search_run.query_final or "")

            # Build filters object for search_iter, and params dict for SourceQuery
            filters_obj = _build_filters(search_run.filters, source)
            filters_applied = translate_for_source(search_run.filters, source)
            filters_hr = humanise_filters(filters_obj, source) if filters_obj is not None else ""

            client = clients[source]
            batch_size = BATCH_SIZES[source]
            total_fetched = 0
            searched_at = datetime.now(UTC)

            # Stream batches and write to DB
            batch_kwarg = "batch_size" if source == "pubmed" else "page_size"
            async for batch in client.search_iter(
                query_string, filters_obj, **{batch_kwarg: batch_size}
            ):
                db_articles = [_to_db_article(a, project_id, search_run_id, source) for a in batch]
                db.add_all(db_articles)
                await db.flush()
                total_fetched += len(batch)
                await ws_manager.broadcast(
                    project_id,
                    {
                        "event": "search_progress",
                        "source": source,
                        "fetched": total_fetched,
                    },
                )

            # Write SourceQuery record
            source_query = SourceQuery(
                id=str(uuid.uuid4()),
                search_run_id=search_run_id,
                source=source,
                interface=SOURCE_INTERFACES[source],
                query_string=query_string,
                filters_applied=filters_applied,
                filters_human_readable=filters_hr or "",
                searched_at=searched_at,
                result_count=total_fetched,
            )
            db.add(source_query)
            await db.flush()

        # Mark completed
        search_run.status = "completed"
        search_run.completed_at = datetime.now(UTC)
        await db.commit()
        await ws_manager.broadcast(
            project_id,
            {"event": "search_complete", "total_articles": total_fetched},
        )

    except Exception as exc:
        search_run.status = "failed"
        await db.commit()
        await ws_manager.broadcast(
            project_id,
            {"event": "search_error", "message": str(exc)},
        )
        raise


def _to_db_article(article, project_id: str, search_run_id: str, source: str) -> Article:
    """Map a package Article model to the DB Article ORM row."""
    authors = [a.model_dump() for a in (article.authors or [])]

    # Source-specific external ID field
    pmid = getattr(article, "pmid", None)
    doi = getattr(article, "doi", None)
    europepmc_id = article.id if source == "europepmc" else None
    semantic_scholar_id = article.id if source == "semanticscholar" else None

    return Article(
        id=str(uuid.uuid4()),
        project_id=project_id,
        search_run_id=search_run_id,
        pmid=pmid,
        doi=doi,
        europepmc_id=europepmc_id,
        semantic_scholar_id=semantic_scholar_id,
        title=article.title,
        abstract=getattr(article, "abstract", None),
        authors=authors,
        journal=getattr(article, "journal", None),
        pub_date=getattr(article, "publication_date", None),
        source=source,
    )
