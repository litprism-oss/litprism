import uuid
from dataclasses import dataclass, field

from db.models import Article, DeduplicationLog
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.parsers import ParsedArticle

_FUZZY_THRESHOLD = 92.0


@dataclass
class DedupResult:
    new_articles: list[ParsedArticle]
    duplicates: list[tuple[ParsedArticle, str, float]]
    # (duplicate_article, match_type, similarity_score)
    # match_type: "doi" | "pmid" | "title_fuzzy"
    duplicate_article_ids: list[str]  # existing DB article IDs that matched incoming records
    # Duplicates of another record in the SAME file: (match_type, score, title, index into
    # new_articles of the record that was kept). The caller logs these once the kept record
    # has a database id.
    batch_duplicates: list[tuple[str, float, str | None, int]] = field(default_factory=list)


async def deduplicate(
    incoming: list[ParsedArticle],
    project_id: str,
    db: AsyncSession,
) -> DedupResult:
    """
    1. Load existing articles for project from DB (id, doi, pmid, title)
    2. Normalise DOIs (lowercase, strip https://doi.org/ prefix)
    3. For each incoming article:
       a. DOI match against existing → duplicate
       b. PMID match against existing → duplicate
       c. Title fuzzy match against existing → duplicate if score ≥ 92
       d. No match → new article, add to "seen" set for within-batch dedup
    4. Return DedupResult
    """
    result = await db.execute(
        select(Article.id, Article.doi, Article.pmid, Article.title).where(
            Article.project_id == project_id
        )
    )
    existing = result.all()

    # Build lookup structures from existing articles
    existing_dois: dict[str, str] = {}  # normalised doi → article_id
    existing_pmids: dict[str, str] = {}  # pmid → article_id
    existing_titles: list[tuple[str, str]] = []  # [(title_lower, article_id), ...]

    for row in existing:
        norm_doi = _normalise_doi(row.doi)
        if norm_doi:
            existing_dois[norm_doi] = row.id
        if row.pmid:
            existing_pmids[row.pmid] = row.id
        if row.title:
            existing_titles.append((row.title.lower(), row.id))

    new_articles: list[ParsedArticle] = []
    duplicates: list[tuple[ParsedArticle, str, float]] = []
    duplicate_article_ids: list[str] = []
    dedup_log_rows: list[DeduplicationLog] = []

    # Within-batch seen sets (prevent inter-batch duplicates being added twice)
    seen_dois: dict[str, int] = {}  # value = index into new_articles
    seen_pmids: dict[str, int] = {}
    seen_titles: list[tuple[str, int]] = []  # for fuzzy matching within batch
    batch_duplicates: list[tuple[str, float, str | None, int]] = []
    kept_index: int | None = None

    for article in incoming:
        norm_doi = _normalise_doi(article.doi)
        match_type: str | None = None
        score: float = 100.0
        kept_id: str | None = None
        kept_index = None

        # --- DOI match ---
        if norm_doi:
            if norm_doi in existing_dois:
                match_type = "doi"
                kept_id = existing_dois[norm_doi]
            elif norm_doi in seen_dois:
                match_type = "doi"
                kept_index = seen_dois[norm_doi]  # within-batch duplicate

        # --- PMID match ---
        if match_type is None and article.pmid:
            if article.pmid in existing_pmids:
                match_type = "pmid"
                kept_id = existing_pmids[article.pmid]
            elif article.pmid in seen_pmids:
                match_type = "pmid"
                kept_index = seen_pmids[article.pmid]

        # --- Title fuzzy match ---
        if match_type is None and article.title:
            title_lower = article.title.lower()
            # Check against existing DB articles
            for existing_title, existing_id in existing_titles:
                s = _title_match(title_lower, existing_title)
                if s >= _FUZZY_THRESHOLD:
                    match_type = "title_fuzzy"
                    score = s
                    kept_id = existing_id
                    break
            # Check within-batch if still no match
            if match_type is None:
                for seen_title, seen_idx in seen_titles:
                    s = _title_match(title_lower, seen_title)
                    if s >= _FUZZY_THRESHOLD:
                        match_type = "title_fuzzy"
                        score = s
                        kept_index = seen_idx  # within-batch
                        break

        if match_type is not None:
            duplicates.append((article, match_type, score))
            if kept_id:
                duplicate_article_ids.append(kept_id)
                dedup_log_rows.append(
                    DeduplicationLog(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        kept_article_id=kept_id,
                        duplicate_article_id=None,
                        duplicate_title=article.title,
                        match_type=match_type,
                        similarity_score=score if match_type == "title_fuzzy" else None,
                    )
                )
            elif kept_index is not None:
                batch_duplicates.append(
                    (
                        match_type,
                        score if match_type == "title_fuzzy" else None,
                        article.title,
                        kept_index,
                    )
                )
        else:
            idx = len(new_articles)
            new_articles.append(article)
            # Add to "seen" sets for within-batch dedup
            if norm_doi:
                seen_dois[norm_doi] = idx
            if article.pmid:
                seen_pmids[article.pmid] = idx
            if article.title:
                seen_titles.append((article.title.lower(), idx))

    for row in dedup_log_rows:
        db.add(row)

    return DedupResult(
        new_articles=new_articles,
        duplicates=duplicates,
        duplicate_article_ids=duplicate_article_ids,
        batch_duplicates=batch_duplicates,
    )


def _normalise_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.lower().strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi


def _title_match(title_a: str, title_b: str) -> float:
    """token_sort_ratio handles word-order differences between sources."""
    return fuzz.token_sort_ratio(title_a.lower(), title_b.lower())
