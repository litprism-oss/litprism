"""Filter translation and PRISMA-S humanisation for litprism-pubmed.

FilterTranslator converts a SearchFilters instance into the native parameter
dict expected by each source's API. The returned dict is stored verbatim in
SourceQuery.filters_applied so the PRISMA-S table shows exactly what was sent.

humanise_filters produces the plain-English summary shown in the PRISMA-S table.
"""

from litprism.pubmed.models import SearchFilters


class FilterTranslator:
    """Translates a unified SearchFilters into source-specific API parameters."""

    @staticmethod
    def to_pubmed(filters: SearchFilters) -> dict:
        """Return dict of E-utilities params and a filter query string fragment.

        The 'filter_query' key (when present) must be AND-ed into the main
        query term by the caller before sending to esearch.
        """
        params: dict = {}
        query_fragments: list[str] = []

        if filters.date_range:
            if filters.date_range.start:
                params["mindate"] = filters.date_range.start.strftime("%Y/%m/%d")
            if filters.date_range.end:
                params["maxdate"] = filters.date_range.end.strftime("%Y/%m/%d")
            params["datetype"] = "pdat"

        for lang in filters.languages:
            query_fragments.append(f'"{lang}"[la]')

        if filters.has_abstract:
            query_fragments.append("hasabstract")

        pubmed_type_map = {
            "journal_article": "Journal Article",
            "review": "Review",
            "systematic_review": "Systematic Review",
            "meta_analysis": "Meta-Analysis",
            "clinical_trial": "Clinical Trial",
            "rct": "Randomized Controlled Trial",
            "case_report": "Case Reports",
            "preprint": "Preprint",
        }
        for pt in filters.publication_types:
            if mapped := pubmed_type_map.get(pt):
                query_fragments.append(f'"{mapped}"[pt]')

        for species in filters.pubmed_species:
            if species == "human":
                query_fragments.append("Humans[MeSH]")
            elif species == "animal":
                query_fragments.append("Animals[MeSH]")

        for sex in filters.pubmed_sex:
            if sex == "male":
                query_fragments.append("Male[MeSH]")
            elif sex == "female":
                query_fragments.append("Female[MeSH]")

        if filters.pubmed_free_full_text:
            query_fragments.append("free full text[filter]")

        if query_fragments:
            params["filter_query"] = " AND ".join(f"({f})" for f in query_fragments)

        return params

    @staticmethod
    def to_europepmc(filters: SearchFilters) -> dict:
        """Return dict with a filter query fragment and Europe PMC API params."""
        query_fragments: list[str] = []
        params: dict = {}

        if filters.date_range:
            start = filters.date_range.start.year if filters.date_range.start else 1800
            end = filters.date_range.end.year if filters.date_range.end else 3000
            query_fragments.append(f"FIRST_PDATE:[{start} TO {end}]")

        for lang in filters.languages:
            query_fragments.append(f"LANG:{lang}")

        epmc_type_map = {
            "journal_article": "journal article",
            "review": "review",
            "systematic_review": "systematic review",
            "meta_analysis": "meta-analysis",
            "clinical_trial": "clinical trial",
            "preprint": "preprint",
            "book_chapter": "book chapter",
        }
        for pt in filters.publication_types:
            if mapped := epmc_type_map.get(pt):
                query_fragments.append(f'PUB_TYPE:"{mapped}"')

        if filters.europepmc_sources:
            sources = " OR ".join(f"SRC:{s}" for s in filters.europepmc_sources)
            query_fragments.append(f"({sources})")

        if filters.europepmc_open_access:
            query_fragments.append("OPEN_ACCESS:Y")

        if filters.has_abstract:
            query_fragments.append("HAS_ABSTRACT:Y")

        params["synonym"] = "true" if filters.europepmc_mesh_synonyms else "false"

        if query_fragments:
            params["filter_query"] = " AND ".join(f"({f})" for f in query_fragments)

        return params

    @staticmethod
    def to_semantic_scholar(filters: SearchFilters) -> dict:
        """Return dict of Semantic Scholar API query params."""
        params: dict = {}

        if filters.date_range:
            start = str(filters.date_range.start.year) if filters.date_range.start else ""
            end = str(filters.date_range.end.year) if filters.date_range.end else ""
            params["year"] = f"{start}-{end}"

        s2_type_map = {
            "journal_article": "JournalArticle",
            "review": "Review",
            "clinical_trial": "ClinicalTrial",
            "conference_paper": "Conference",
            "preprint": "Preprint",
            "book_chapter": "Book",
        }
        mapped_types = [s2_type_map[pt] for pt in filters.publication_types if pt in s2_type_map]
        if mapped_types:
            params["publicationTypes"] = ",".join(mapped_types)

        if filters.semanticscholar_fields_of_study:
            params["fieldsOfStudy"] = ",".join(filters.semanticscholar_fields_of_study)

        if filters.semanticscholar_open_access_pdf:
            params["openAccessPdf"] = ""  # presence of param enables filter

        if filters.semanticscholar_min_citation_count is not None:
            params["minCitationCount"] = str(filters.semanticscholar_min_citation_count)

        if filters.semanticscholar_venues:
            params["venue"] = ",".join(filters.semanticscholar_venues)

        return params


def humanise_filters(filters: SearchFilters, source: str) -> str:
    """Return a plain-English summary of applied filters for the PRISMA-S table."""
    parts: list[str] = []

    if filters.date_range:
        start = filters.date_range.start.year if filters.date_range.start else "earliest"
        end = filters.date_range.end.year if filters.date_range.end else "present"
        parts.append(f"Date: {start}\u2013{end}")

    if filters.languages:
        parts.append(f"Language: {', '.join(filters.languages)}")

    if filters.publication_types:
        parts.append(f"Publication types: {', '.join(filters.publication_types)}")

    if filters.has_abstract:
        parts.append("Abstracts only")

    if source == "pubmed" and filters.pubmed_species:
        parts.append(f"Species: {', '.join(filters.pubmed_species)}")

    if source == "europepmc" and filters.europepmc_open_access:
        parts.append("Open access only")

    if source == "semanticscholar" and filters.semanticscholar_fields_of_study:
        parts.append(f"Fields: {', '.join(filters.semanticscholar_fields_of_study)}")

    return "; ".join(parts) if parts else "None"
