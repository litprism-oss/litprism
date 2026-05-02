import asyncio
import io
import logging
import re

import httpx
from config import settings
from db.models import Article
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PMC_OA_BASE = "https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi"
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNPAYWALL_BASE = "https://api.unpaywall.org/v2"


async def retrieve_fulltext_for_project(
    project_id: str,
    db: AsyncSession,
) -> dict[str, int]:
    """Retrieve full text for all articles in a project that haven't been attempted yet."""
    result = await db.execute(
        select(Article).where(
            Article.project_id == project_id,
            Article.fulltext_text.is_(None),
            Article.fulltext_status.is_(None),
        )
    )
    articles = result.scalars().all()

    if not articles:
        return {"retrieved": 0, "unavailable": 0, "errors": 0}

    for a in articles:
        a.fulltext_status = "pending"
    await db.commit()

    counts = {"retrieved": 0, "unavailable": 0, "errors": 0}

    async with httpx.AsyncClient(timeout=30.0) as http:
        for article in articles:
            try:
                text, source = await _retrieve_one(article, http)
                if text:
                    article.fulltext_text = _truncate(text, max_words=8000)
                    article.fulltext_source = source
                    article.fulltext_status = "retrieved"
                    counts["retrieved"] += 1
                else:
                    article.fulltext_status = "unavailable"
                    counts["unavailable"] += 1
            except Exception as e:
                logger.warning("Full text retrieval failed for article %s: %s", article.id, e)
                article.fulltext_status = "error"
                counts["errors"] += 1

            await db.commit()
            await asyncio.sleep(0.3)

    logger.info("Full text retrieval complete for project %s: %s", project_id, counts)
    return counts


async def _retrieve_one(
    article: Article,
    http: httpx.AsyncClient,
) -> tuple[str | None, str | None]:
    """Try retrieval tiers in order. Returns (text, source) or (None, None)."""
    # Tier 1 — PMC Open Access
    pmcid = await _get_pmcid(article, http)
    if pmcid:
        text = await _fetch_pmc_oa(pmcid, http)
        if text:
            return text, "pmc_oa"

    # Tier 2 — Unpaywall PDF
    if article.doi:
        pdf_url = await _get_unpaywall_pdf_url(article.doi, http)
        if pdf_url:
            text = await _extract_pdf_text(pdf_url, http)
            if text:
                return text, "unpaywall_pdf"

    return None, None


async def _get_pmcid(
    article: Article,
    http: httpx.AsyncClient,
) -> str | None:
    """Resolve PMID → PMCID via E-utilities elink."""
    if not article.pmid:
        return None

    params: dict = {
        "dbfrom": "pubmed",
        "db": "pmc",
        "id": article.pmid,
        "retmode": "json",
    }
    if settings.pubmed_api_key:
        params["api_key"] = settings.pubmed_api_key

    try:
        resp = await http.get(f"{EUTILS_BASE}/elink.fcgi", params=params)
        resp.raise_for_status()
        data = resp.json()
        for linkset in data.get("linksets", []):
            for linksetdb in linkset.get("linksetdbs", []):
                if linksetdb.get("dbto") == "pmc":
                    ids = linksetdb.get("links", [])
                    if ids:
                        return str(ids[0])
    except Exception as e:
        logger.debug("PMCID lookup failed for pmid=%s: %s", article.pmid, e)

    return None


async def _fetch_pmc_oa(
    pmcid: str,
    http: httpx.AsyncClient,
) -> str | None:
    """Fetch full text from PMC OA subset via OAI-PMH. Returns plain text or None."""
    try:
        resp = await http.get(
            PMC_OA_BASE,
            params={
                "verb": "GetRecord",
                "identifier": f"oai:pubmedcentral.nih.gov:{pmcid}",
                "metadataPrefix": "pmc",
            },
        )
        resp.raise_for_status()

        xml = resp.text
        text = re.sub(r"<[^>]+>", " ", xml)
        text = re.sub(r"\s+", " ", text).strip()

        # OAI returns metadata even for non-OA articles — require substantial body
        if len(text) > 500:
            return text
    except Exception as e:
        logger.debug("PMC OA fetch failed for pmcid=%s: %s", pmcid, e)

    return None


async def _get_unpaywall_pdf_url(
    doi: str,
    http: httpx.AsyncClient,
) -> str | None:
    """Query Unpaywall for an open-access PDF URL. Returns best PDF URL or None."""
    if not settings.unpaywall_email:
        logger.debug("unpaywall_email not set — skipping Unpaywall")
        return None

    try:
        resp = await http.get(
            f"{UNPAYWALL_BASE}/{doi}",
            params={"email": settings.unpaywall_email},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

        best = data.get("best_oa_location")
        if best and best.get("url_for_pdf"):
            return best["url_for_pdf"]

        for loc in data.get("oa_locations", []):
            if loc.get("url_for_pdf"):
                return loc["url_for_pdf"]

    except Exception as e:
        logger.debug("Unpaywall lookup failed for doi=%s: %s", doi, e)

    return None


async def _extract_pdf_text(
    pdf_url: str,
    http: httpx.AsyncClient,
) -> str | None:
    """Download a PDF and extract text with pdfplumber. Returns text or None."""
    try:
        import pdfplumber

        resp = await http.get(pdf_url, follow_redirects=True)
        resp.raise_for_status()

        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            pages = []
            for page in pdf.pages[:30]:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
            full_text = "\n".join(pages)

        if len(full_text.strip()) > 200:
            return full_text

    except Exception as e:
        logger.debug("PDF extraction failed for url=%s: %s", pdf_url, e)

    return None


def _truncate(text: str, max_words: int = 8000) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "\n\n[Truncated to 8,000 words]"
