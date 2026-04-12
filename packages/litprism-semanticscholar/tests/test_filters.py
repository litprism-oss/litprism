"""Unit tests for litprism-semanticscholar filter translation."""

from datetime import date

from litprism.semanticscholar.filters import FilterTranslator, humanise_filters
from litprism.semanticscholar.models import DateRange, SearchFilters


class TestFilterTranslatorToSemanticScholar:
    def test_empty_filters_returns_empty_dict(self):
        filters = SearchFilters()
        result = FilterTranslator.to_semanticscholar(filters)
        assert result == {}

    def test_date_range_both_bounds(self):
        filters = SearchFilters(
            date_range=DateRange(start=date(2020, 1, 1), end=date(2023, 12, 31))
        )
        result = FilterTranslator.to_semanticscholar(filters)
        assert result["publicationDateOrYear"] == "2020-01-01:2023-12-31"

    def test_date_range_start_only(self):
        filters = SearchFilters(date_range=DateRange(start=date(2020, 1, 1)))
        result = FilterTranslator.to_semanticscholar(filters)
        assert result["publicationDateOrYear"].startswith("2020-01-01:")

    def test_date_range_end_only(self):
        filters = SearchFilters(date_range=DateRange(end=date(2023, 12, 31)))
        result = FilterTranslator.to_semanticscholar(filters)
        assert result["publicationDateOrYear"].endswith(":2023-12-31")

    def test_publication_types_mapped(self):
        filters = SearchFilters(publication_types=["journal_article", "review"])
        result = FilterTranslator.to_semanticscholar(filters)
        types = set(result["publicationTypes"].split(","))
        assert "JournalArticle" in types
        assert "Review" in types

    def test_publication_types_deduplicates(self):
        # systematic_review and review both map to "Review"
        filters = SearchFilters(publication_types=["review", "systematic_review"])
        result = FilterTranslator.to_semanticscholar(filters)
        types = result["publicationTypes"].split(",")
        assert types.count("Review") == 1

    def test_unknown_publication_type_ignored(self):
        filters = SearchFilters(publication_types=["unknown_type"])
        result = FilterTranslator.to_semanticscholar(filters)
        assert "publicationTypes" not in result

    def test_fields_of_study(self):
        filters = SearchFilters(semanticscholar_fields_of_study=["Medicine", "Biology"])
        result = FilterTranslator.to_semanticscholar(filters)
        assert result["fieldsOfStudy"] == "Medicine,Biology"

    def test_open_access_pdf(self):
        filters = SearchFilters(semanticscholar_open_access_pdf=True)
        result = FilterTranslator.to_semanticscholar(filters)
        assert "openAccessPdf" in result

    def test_min_citation_count(self):
        filters = SearchFilters(semanticscholar_min_citation_count=50)
        result = FilterTranslator.to_semanticscholar(filters)
        assert result["minCitationCount"] == "50"

    def test_venues(self):
        filters = SearchFilters(semanticscholar_venues=["Nature", "Science"])
        result = FilterTranslator.to_semanticscholar(filters)
        assert result["venue"] == "Nature,Science"

    def test_non_ss_fields_ignored(self):
        """PubMed- and EuropePMC-specific fields must not appear in output."""
        filters = SearchFilters(
            pubmed_species=["human"],
            europepmc_open_access=True,
        )
        result = FilterTranslator.to_semanticscholar(filters)
        assert result == {}


class TestHumaniseFilters:
    def test_no_filters_returns_none(self):
        assert humanise_filters(SearchFilters()) == "None"

    def test_date_range_appears(self):
        filters = SearchFilters(
            date_range=DateRange(start=date(2020, 1, 1), end=date(2023, 12, 31))
        )
        result = humanise_filters(filters)
        assert "2020-01-01" in result
        assert "2023-12-31" in result

    def test_fields_of_study_appears(self):
        filters = SearchFilters(semanticscholar_fields_of_study=["Medicine"])
        result = humanise_filters(filters)
        assert "Medicine" in result

    def test_open_access_pdf_appears(self):
        filters = SearchFilters(semanticscholar_open_access_pdf=True)
        result = humanise_filters(filters)
        assert "Open access PDF" in result

    def test_min_citations_appears(self):
        filters = SearchFilters(semanticscholar_min_citation_count=100)
        result = humanise_filters(filters)
        assert "100" in result

    def test_multiple_parts_joined_by_semicolon(self):
        filters = SearchFilters(
            semanticscholar_fields_of_study=["Medicine"],
            semanticscholar_min_citation_count=10,
        )
        result = humanise_filters(filters)
        assert "; " in result
