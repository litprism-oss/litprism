"""Filter translation and PRISMA-S humanisation for litprism-europepmc.

FilterTranslator converts a SearchFilters instance into the native parameter
dict expected by the Europe PMC REST API. The returned dict is stored verbatim
in SourceQuery.filters_applied so the PRISMA-S table shows exactly what was sent.

humanise_filters produces the plain-English summary shown in the PRISMA-S table.
"""

from litprism.europepmc.models import SearchFilters


class FilterTranslator:
    """Translates a unified SearchFilters into Europe PMC API parameters."""

    @staticmethod
    def to_europepmc(filters: SearchFilters) -> dict:
        """Return dict with a filter query fragment and Europe PMC API params.

        The 'filter_query' key (when present) must be AND-ed into the main
        query term by the caller before sending to the search endpoint.
        """
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


def humanise_filters(filters: SearchFilters) -> str:
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

    if filters.europepmc_open_access:
        parts.append("Open access only")

    if filters.europepmc_sources and filters.europepmc_sources != ["MED"]:
        parts.append(f"Sources: {', '.join(filters.europepmc_sources)}")

    return "; ".join(parts) if parts else "None"
