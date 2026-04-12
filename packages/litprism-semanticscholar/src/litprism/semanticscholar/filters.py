"""Filter translation and PRISMA-S humanisation for litprism-semanticscholar.

FilterTranslator converts a SearchFilters instance into the native parameter
dict expected by the Semantic Scholar Graph API. The returned dict is passed
directly as query parameters to the search endpoint.

humanise_filters produces the plain-English summary shown in the PRISMA-S table.
"""

from litprism.semanticscholar.models import SearchFilters

# Map from unified publication_types to Semantic Scholar publicationTypes values.
# SS types: JournalArticle, Conference, Review, Book, BookSection, Preprint,
#           ClinicalTrial, CaseReport, MetaAnalysis, Editorial, LettersAndComments, News, Study
_SS_TYPE_MAP: dict[str, str] = {
    "journal_article": "JournalArticle",
    "review": "Review",
    "systematic_review": "Review",
    "meta_analysis": "MetaAnalysis",
    "clinical_trial": "ClinicalTrial",
    "rct": "ClinicalTrial",
    "case_report": "CaseReport",
    "conference_paper": "Conference",
    "preprint": "Preprint",
    "book_chapter": "BookSection",
}


class FilterTranslator:
    """Translates a unified SearchFilters into Semantic Scholar API parameters."""

    @staticmethod
    def to_semanticscholar(filters: SearchFilters) -> dict:
        """Return dict of Semantic Scholar query parameters derived from filters.

        The returned dict is merged with the base search params by the caller.
        Deduplication is applied to publicationTypes values.
        """
        params: dict = {}

        if filters.date_range:
            start = filters.date_range.start.isoformat() if filters.date_range.start else "1800"
            end = filters.date_range.end.isoformat() if filters.date_range.end else "3000"
            params["publicationDateOrYear"] = f"{start}:{end}"

        if filters.publication_types:
            mapped = {_SS_TYPE_MAP[pt] for pt in filters.publication_types if pt in _SS_TYPE_MAP}
            if mapped:
                params["publicationTypes"] = ",".join(sorted(mapped))

        if filters.semanticscholar_fields_of_study:
            params["fieldsOfStudy"] = ",".join(filters.semanticscholar_fields_of_study)

        if filters.semanticscholar_open_access_pdf:
            params["openAccessPdf"] = ""

        if filters.semanticscholar_min_citation_count is not None:
            params["minCitationCount"] = str(filters.semanticscholar_min_citation_count)

        if filters.semanticscholar_venues:
            params["venue"] = ",".join(filters.semanticscholar_venues)

        return params


def humanise_filters(filters: SearchFilters) -> str:
    """Return a plain-English summary of applied filters for the PRISMA-S table."""
    parts: list[str] = []

    if filters.date_range:
        start = filters.date_range.start.isoformat() if filters.date_range.start else "earliest"
        end = filters.date_range.end.isoformat() if filters.date_range.end else "present"
        parts.append(f"Date: {start}\u2013{end}")

    if filters.languages:
        parts.append(f"Language: {', '.join(filters.languages)}")

    if filters.publication_types:
        parts.append(f"Publication types: {', '.join(filters.publication_types)}")

    if filters.semanticscholar_fields_of_study:
        parts.append(f"Fields of study: {', '.join(filters.semanticscholar_fields_of_study)}")

    if filters.semanticscholar_open_access_pdf:
        parts.append("Open access PDF only")

    if filters.semanticscholar_min_citation_count is not None:
        parts.append(f"Min citations: {filters.semanticscholar_min_citation_count}")

    if filters.semanticscholar_venues:
        parts.append(f"Venues: {', '.join(filters.semanticscholar_venues)}")

    return "; ".join(parts) if parts else "None"
