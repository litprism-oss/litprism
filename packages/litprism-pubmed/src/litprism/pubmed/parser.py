"""XML → Pydantic parser for NCBI E-utilities efetch responses."""

import contextlib
import xml.etree.ElementTree as ET
from datetime import date

from litprism.pubmed.exceptions import PubMedParseError
from litprism.pubmed.models import Article, Author


def _text(element: ET.Element | None, default: str | None = None) -> str | None:
    if element is None:
        return default
    return (element.text or "").strip() or default


def _parse_date(article_date: ET.Element | None) -> tuple[date | None, int | None]:
    """Parse a PubDate element into (date, year)."""
    if article_date is None:
        return None, None
    year_el = article_date.find("Year")
    month_el = article_date.find("Month")
    day_el = article_date.find("Day")
    medline_date_el = article_date.find("MedlineDate")

    year: int | None = None
    if year_el is not None and year_el.text:
        with contextlib.suppress(ValueError):
            year = int(year_el.text.strip())
    elif medline_date_el is not None and medline_date_el.text:
        # e.g. "2021 Jan-Feb" — extract year
        with contextlib.suppress(ValueError):
            year = int(medline_date_el.text.strip()[:4])

    if year is None:
        return None, None

    month_str = _text(month_el) or "Jan"
    day_str = _text(day_el) or "1"
    month_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    try:
        month = int(month_str) if month_str.isdigit() else month_map.get(month_str[:3], 1)
        day = int(day_str)
        pub_date = date(year, month, day)
    except (ValueError, KeyError):
        pub_date = None

    return pub_date, year


def _parse_authors(article: ET.Element) -> list[Author]:
    authors = []
    for author_el in article.findall(".//AuthorList/Author"):
        last = _text(author_el.find("LastName"))
        fore = _text(author_el.find("ForeName")) or _text(author_el.find("Initials"))
        affiliation_el = author_el.find(".//AffiliationInfo/Affiliation")
        affiliation = _text(affiliation_el)
        identifier_el = author_el.find("Identifier[@Source='ORCID']")
        orcid = _text(identifier_el)
        if last:
            authors.append(
                Author(last_name=last, fore_name=fore, affiliation=affiliation, orcid=orcid)
            )
    return authors


def parse_article(pubmed_article: ET.Element) -> Article | None:
    """Parse a single PubmedArticle element into an Article.

    Returns None if the element is malformed or missing required fields.
    """
    medline = pubmed_article.find("MedlineCitation")
    if medline is None:
        return None

    pmid_el = medline.find("PMID")
    pmid = _text(pmid_el)
    if not pmid:
        return None

    article_el = medline.find("Article")
    if article_el is None:
        return None

    title = _text(article_el.find("ArticleTitle")) or ""
    abstract_parts = [(el.text or "").strip() for el in article_el.findall(".//AbstractText")]
    abstract = " ".join(p for p in abstract_parts if p) or None

    journal_el = article_el.find("Journal")
    journal = _text(journal_el.find("Title") if journal_el is not None else None)

    pub_date_el = None
    if journal_el is not None:
        pub_date_el = journal_el.find(".//PubDate")
    pub_date, pub_year = _parse_date(pub_date_el)

    authors = _parse_authors(article_el)

    mesh_terms = [
        _text(mh.find("DescriptorName"))
        for mh in medline.findall(".//MeshHeadingList/MeshHeading")
        if _text(mh.find("DescriptorName"))
    ]

    keywords = [_text(kw) for kw in medline.findall(".//KeywordList/Keyword") if _text(kw)]

    article_types = [
        _text(pt)
        for pt in article_el.findall(".//PublicationTypeList/PublicationType")
        if _text(pt)
    ]

    # DOI
    doi = None
    for location in article_el.findall(".//ELocationID"):
        if location.get("EIdType") == "doi":
            doi = _text(location)
            break
    if doi is None:
        pubmed_data = pubmed_article.find("PubmedData")
        if pubmed_data is not None:
            for article_id in pubmed_data.findall(".//ArticleIdList/ArticleId"):
                if article_id.get("IdType") == "doi":
                    doi = _text(article_id)
                    break

    # Open access / PMC
    pmc_url = None
    pubmed_data = pubmed_article.find("PubmedData")
    if pubmed_data is not None:
        for article_id in pubmed_data.findall(".//ArticleIdList/ArticleId"):
            if article_id.get("IdType") == "pmc":
                pmc_id = _text(article_id)
                if pmc_id:
                    pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/"
                    break

    return Article(
        id=pmid,
        pmid=pmid,
        doi=doi,
        title=title,
        abstract=abstract,
        authors=authors,
        journal=journal,
        publication_date=pub_date,
        publication_year=pub_year,
        mesh_terms=[t for t in mesh_terms if t],
        keywords=[k for k in keywords if k],
        article_types=[a for a in article_types if a],
        open_access=pmc_url is not None,
        full_text_url=pmc_url,
    )


def parse_xml(xml_string: str) -> list[Article]:
    """Parse an efetch XML response into a list of Articles.

    Malformed individual articles are skipped; a fully unparseable response
    raises PubMedParseError.
    """
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as exc:
        raise PubMedParseError(f"Failed to parse efetch XML: {exc}") from exc

    articles = []
    for pubmed_article in root.findall(".//PubmedArticle"):
        article = parse_article(pubmed_article)
        if article is not None:
            articles.append(article)
    return articles
