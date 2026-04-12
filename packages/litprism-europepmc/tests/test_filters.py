"""Unit tests for litprism-europepmc FilterTranslator and humanise_filters."""

from datetime import date

from litprism.europepmc.filters import FilterTranslator, humanise_filters
from litprism.europepmc.models import DateRange, SearchFilters


class TestFilterTranslatorToEuropePMC:
    def test_no_filters_except_default_source(self):
        # Default europepmc_sources=["MED"] always produces a SRC: fragment.
        filters = SearchFilters()
        result = FilterTranslator.to_europepmc(filters)
        assert result["synonym"] == "true"
        assert "filter_query" in result
        assert "SRC:MED" in result["filter_query"]

    def test_empty_sources_no_filter_query(self):
        # Explicitly clearing sources (and no other filters) → no filter_query.
        filters = SearchFilters(europepmc_sources=[])
        result = FilterTranslator.to_europepmc(filters)
        assert result == {"synonym": "true"}
        assert "filter_query" not in result

    def test_date_range_full(self):
        filters = SearchFilters(
            date_range=DateRange(start=date(2015, 1, 1), end=date(2023, 12, 31))
        )
        result = FilterTranslator.to_europepmc(filters)
        assert "filter_query" in result
        assert "FIRST_PDATE:[2015 TO 2023]" in result["filter_query"]

    def test_date_range_open_start(self):
        filters = SearchFilters(date_range=DateRange(end=date(2023, 12, 31)))
        result = FilterTranslator.to_europepmc(filters)
        assert "FIRST_PDATE:[1800 TO 2023]" in result["filter_query"]

    def test_date_range_open_end(self):
        filters = SearchFilters(date_range=DateRange(start=date(2020, 1, 1)))
        result = FilterTranslator.to_europepmc(filters)
        assert "FIRST_PDATE:[2020 TO 3000]" in result["filter_query"]

    def test_language_filter(self):
        filters = SearchFilters(languages=["en", "fr"])
        result = FilterTranslator.to_europepmc(filters)
        assert "LANG:en" in result["filter_query"]
        assert "LANG:fr" in result["filter_query"]

    def test_publication_types_mapped(self):
        filters = SearchFilters(publication_types=["systematic_review", "meta_analysis"])
        result = FilterTranslator.to_europepmc(filters)
        assert 'PUB_TYPE:"systematic review"' in result["filter_query"]
        assert 'PUB_TYPE:"meta-analysis"' in result["filter_query"]

    def test_publication_type_unmapped_ignored(self):
        # "rct" has no Europe PMC mapping — only the default SRC:MED appears.
        filters = SearchFilters(publication_types=["rct"])
        result = FilterTranslator.to_europepmc(filters)
        assert "PUB_TYPE" not in result.get("filter_query", "")

    def test_open_access_filter(self):
        filters = SearchFilters(europepmc_open_access=True)
        result = FilterTranslator.to_europepmc(filters)
        assert "OPEN_ACCESS:Y" in result["filter_query"]

    def test_has_abstract_filter(self):
        filters = SearchFilters(has_abstract=True)
        result = FilterTranslator.to_europepmc(filters)
        assert "HAS_ABSTRACT:Y" in result["filter_query"]

    def test_default_med_source(self):
        filters = SearchFilters()
        result = FilterTranslator.to_europepmc(filters)
        assert "filter_query" in result
        assert "SRC:MED" in result["filter_query"]

    def test_multiple_sources(self):
        filters = SearchFilters(europepmc_sources=["MED", "PMC", "PPR"])
        result = FilterTranslator.to_europepmc(filters)
        assert "SRC:MED" in result["filter_query"]
        assert "SRC:PMC" in result["filter_query"]
        assert "SRC:PPR" in result["filter_query"]

    def test_mesh_synonyms_disabled(self):
        filters = SearchFilters(europepmc_mesh_synonyms=False)
        result = FilterTranslator.to_europepmc(filters)
        assert result["synonym"] == "false"


class TestHumaniseFilters:
    def test_empty_filters_returns_none(self):
        filters = SearchFilters(europepmc_sources=[])
        assert humanise_filters(filters) == "None"

    def test_date_range_summary(self):
        filters = SearchFilters(
            date_range=DateRange(start=date(2015, 1, 1), end=date(2023, 12, 31)),
            europepmc_sources=[],
        )
        result = humanise_filters(filters)
        assert "Date: 2015–2023" in result

    def test_open_date_bounds(self):
        filters = SearchFilters(date_range=DateRange(), europepmc_sources=[])
        result = humanise_filters(filters)
        assert "Date: earliest–present" in result

    def test_language_summary(self):
        filters = SearchFilters(languages=["en"], europepmc_sources=[])
        result = humanise_filters(filters)
        assert "Language: en" in result

    def test_open_access_summary(self):
        filters = SearchFilters(europepmc_open_access=True, europepmc_sources=[])
        result = humanise_filters(filters)
        assert "Open access only" in result

    def test_non_default_sources_shown(self):
        filters = SearchFilters(europepmc_sources=["PMC", "PPR"])
        result = humanise_filters(filters)
        assert "Sources:" in result
