"""Tests for litprism.pubmed.filters — FilterTranslator and humanise_filters."""

from datetime import date

from litprism.pubmed.filters import FilterTranslator, humanise_filters
from litprism.pubmed.models import DateRange, SearchFilters

# ---------------------------------------------------------------------------
# FilterTranslator.to_pubmed
# ---------------------------------------------------------------------------


class TestToPubmedDateRange:
    def test_date_range_sets_mindate_maxdate_datetype(self):
        filters = SearchFilters(
            date_range=DateRange(start=date(2015, 1, 1), end=date(2024, 12, 31))
        )
        params = FilterTranslator.to_pubmed(filters)
        assert params["mindate"] == "2015/01/01"
        assert params["maxdate"] == "2024/12/31"
        assert params["datetype"] == "pdat"

    def test_date_range_start_only(self):
        filters = SearchFilters(date_range=DateRange(start=date(2020, 6, 1)))
        params = FilterTranslator.to_pubmed(filters)
        assert params["mindate"] == "2020/06/01"
        assert "maxdate" not in params
        assert params["datetype"] == "pdat"

    def test_date_range_end_only(self):
        filters = SearchFilters(date_range=DateRange(end=date(2023, 3, 15)))
        params = FilterTranslator.to_pubmed(filters)
        assert "mindate" not in params
        assert params["maxdate"] == "2023/03/15"
        assert params["datetype"] == "pdat"

    def test_no_date_range_omits_date_params(self):
        params = FilterTranslator.to_pubmed(SearchFilters())
        assert "mindate" not in params
        assert "maxdate" not in params
        assert "datetype" not in params


class TestToPubmedPublicationTypes:
    def test_publication_types_appear_as_pt_tags(self):
        filters = SearchFilters(publication_types=["clinical_trial", "review"])
        params = FilterTranslator.to_pubmed(filters)
        assert '"Clinical Trial"[pt]' in params["filter_query"]
        assert '"Review"[pt]' in params["filter_query"]

    def test_all_mapped_publication_types(self):
        all_types = [
            "journal_article", "review", "systematic_review", "meta_analysis",
            "clinical_trial", "rct", "case_report", "preprint",
        ]
        filters = SearchFilters(publication_types=all_types)
        params = FilterTranslator.to_pubmed(filters)
        fq = params["filter_query"]
        assert '"Journal Article"[pt]' in fq
        assert '"Systematic Review"[pt]' in fq
        assert '"Meta-Analysis"[pt]' in fq
        assert '"Randomized Controlled Trial"[pt]' in fq
        assert '"Case Reports"[pt]' in fq
        assert '"Preprint"[pt]' in fq

    def test_unknown_publication_type_is_ignored(self):
        filters = SearchFilters(publication_types=["unknown_type"])
        params = FilterTranslator.to_pubmed(filters)
        assert "filter_query" not in params

    def test_conference_paper_not_mapped_for_pubmed(self):
        # conference_paper has no PubMed equivalent in the spec map
        filters = SearchFilters(publication_types=["conference_paper"])
        params = FilterTranslator.to_pubmed(filters)
        assert "filter_query" not in params


class TestToPubmedLanguages:
    def test_single_language(self):
        filters = SearchFilters(languages=["en"])
        params = FilterTranslator.to_pubmed(filters)
        assert '"en"[la]' in params["filter_query"]

    def test_multiple_languages(self):
        filters = SearchFilters(languages=["en", "fr", "de"])
        params = FilterTranslator.to_pubmed(filters)
        fq = params["filter_query"]
        assert '"en"[la]' in fq
        assert '"fr"[la]' in fq
        assert '"de"[la]' in fq


class TestToPubmedHasAbstract:
    def test_has_abstract_adds_fragment(self):
        filters = SearchFilters(has_abstract=True)
        params = FilterTranslator.to_pubmed(filters)
        assert "hasabstract" in params["filter_query"]

    def test_has_abstract_false_omits_fragment(self):
        filters = SearchFilters(has_abstract=False)
        params = FilterTranslator.to_pubmed(filters)
        assert "filter_query" not in params


class TestToPubmedSpeciesAndSex:
    def test_human_species(self):
        filters = SearchFilters(pubmed_species=["human"])
        params = FilterTranslator.to_pubmed(filters)
        assert "Humans[MeSH]" in params["filter_query"]

    def test_animal_species(self):
        filters = SearchFilters(pubmed_species=["animal"])
        params = FilterTranslator.to_pubmed(filters)
        assert "Animals[MeSH]" in params["filter_query"]

    def test_male_sex(self):
        filters = SearchFilters(pubmed_sex=["male"])
        params = FilterTranslator.to_pubmed(filters)
        assert "Male[MeSH]" in params["filter_query"]

    def test_female_sex(self):
        filters = SearchFilters(pubmed_sex=["female"])
        params = FilterTranslator.to_pubmed(filters)
        assert "Female[MeSH]" in params["filter_query"]

    def test_unknown_species_is_ignored(self):
        filters = SearchFilters(pubmed_species=["fish"])
        params = FilterTranslator.to_pubmed(filters)
        assert "filter_query" not in params


class TestToPubmedFreeFullText:
    def test_free_full_text_adds_fragment(self):
        filters = SearchFilters(pubmed_free_full_text=True)
        params = FilterTranslator.to_pubmed(filters)
        assert "free full text[filter]" in params["filter_query"]

    def test_free_full_text_false_omits_fragment(self):
        params = FilterTranslator.to_pubmed(SearchFilters())
        assert "filter_query" not in params


class TestToPubmedFilterQueryFormat:
    def test_multiple_fragments_joined_with_and(self):
        filters = SearchFilters(languages=["en"], has_abstract=True)
        params = FilterTranslator.to_pubmed(filters)
        # Each fragment is wrapped in parentheses and joined with AND
        assert " AND " in params["filter_query"]
        assert params["filter_query"].startswith("(")

    def test_empty_filters_produce_no_filter_query(self):
        params = FilterTranslator.to_pubmed(SearchFilters())
        assert "filter_query" not in params


# ---------------------------------------------------------------------------
# FilterTranslator.to_europepmc
# ---------------------------------------------------------------------------


class TestToEuropePMC:
    def test_date_range_uses_year_bounds(self):
        filters = SearchFilters(
            date_range=DateRange(start=date(2015, 3, 1), end=date(2024, 11, 30))
        )
        params = FilterTranslator.to_europepmc(filters)
        assert "FIRST_PDATE:[2015 TO 2024]" in params["filter_query"]

    def test_date_range_no_start_uses_1800(self):
        filters = SearchFilters(date_range=DateRange(end=date(2020, 1, 1)))
        params = FilterTranslator.to_europepmc(filters)
        assert "FIRST_PDATE:[1800 TO 2020]" in params["filter_query"]

    def test_date_range_no_end_uses_3000(self):
        filters = SearchFilters(date_range=DateRange(start=date(2010, 1, 1)))
        params = FilterTranslator.to_europepmc(filters)
        assert "FIRST_PDATE:[2010 TO 3000]" in params["filter_query"]

    def test_language_filter(self):
        filters = SearchFilters(languages=["en"])
        params = FilterTranslator.to_europepmc(filters)
        assert "LANG:en" in params["filter_query"]

    def test_publication_types_mapped(self):
        filters = SearchFilters(publication_types=["systematic_review", "preprint"])
        params = FilterTranslator.to_europepmc(filters)
        fq = params["filter_query"]
        assert 'PUB_TYPE:"systematic review"' in fq
        assert 'PUB_TYPE:"preprint"' in fq

    def test_sources_filter(self):
        filters = SearchFilters(europepmc_sources=["MED", "PMC"])
        params = FilterTranslator.to_europepmc(filters)
        assert "SRC:MED" in params["filter_query"]
        assert "SRC:PMC" in params["filter_query"]

    def test_open_access_filter(self):
        filters = SearchFilters(europepmc_open_access=True)
        params = FilterTranslator.to_europepmc(filters)
        assert "OPEN_ACCESS:Y" in params["filter_query"]

    def test_has_abstract_filter(self):
        filters = SearchFilters(has_abstract=True)
        params = FilterTranslator.to_europepmc(filters)
        assert "HAS_ABSTRACT:Y" in params["filter_query"]

    def test_mesh_synonyms_true(self):
        filters = SearchFilters(europepmc_mesh_synonyms=True)
        params = FilterTranslator.to_europepmc(filters)
        assert params["synonym"] == "true"

    def test_mesh_synonyms_false(self):
        filters = SearchFilters(europepmc_mesh_synonyms=False)
        params = FilterTranslator.to_europepmc(filters)
        assert params["synonym"] == "false"

    def test_empty_filters_no_filter_query(self):
        # Default europepmc_sources=["MED"] still generates a filter_query
        filters = SearchFilters(europepmc_sources=[])
        params = FilterTranslator.to_europepmc(filters)
        # No fragments other than synonym
        assert "filter_query" not in params
        assert "synonym" in params


# ---------------------------------------------------------------------------
# FilterTranslator.to_semantic_scholar
# ---------------------------------------------------------------------------


class TestToSemanticScholar:
    def test_year_range_both_bounds(self):
        filters = SearchFilters(
            date_range=DateRange(start=date(2020, 1, 1), end=date(2024, 12, 31))
        )
        params = FilterTranslator.to_semantic_scholar(filters)
        assert params["year"] == "2020-2024"

    def test_year_range_start_only(self):
        filters = SearchFilters(date_range=DateRange(start=date(2018, 1, 1)))
        params = FilterTranslator.to_semantic_scholar(filters)
        assert params["year"] == "2018-"

    def test_year_range_end_only(self):
        filters = SearchFilters(date_range=DateRange(end=date(2022, 12, 31)))
        params = FilterTranslator.to_semantic_scholar(filters)
        assert params["year"] == "-2022"

    def test_publication_types_mapped(self):
        filters = SearchFilters(
            publication_types=["journal_article", "review", "conference_paper", "preprint"]
        )
        params = FilterTranslator.to_semantic_scholar(filters)
        assert "JournalArticle" in params["publicationTypes"]
        assert "Review" in params["publicationTypes"]
        assert "Conference" in params["publicationTypes"]
        assert "Preprint" in params["publicationTypes"]

    def test_unmapped_publication_types_excluded(self):
        filters = SearchFilters(publication_types=["rct", "case_report"])
        params = FilterTranslator.to_semantic_scholar(filters)
        assert "publicationTypes" not in params

    def test_fields_of_study(self):
        filters = SearchFilters(
            semanticscholar_fields_of_study=["Medicine", "Biology"]
        )
        params = FilterTranslator.to_semantic_scholar(filters)
        assert "Medicine" in params["fieldsOfStudy"]
        assert "Biology" in params["fieldsOfStudy"]

    def test_open_access_pdf(self):
        filters = SearchFilters(semanticscholar_open_access_pdf=True)
        params = FilterTranslator.to_semantic_scholar(filters)
        assert "openAccessPdf" in params

    def test_open_access_pdf_false_omitted(self):
        params = FilterTranslator.to_semantic_scholar(SearchFilters())
        assert "openAccessPdf" not in params

    def test_min_citation_count(self):
        filters = SearchFilters(semanticscholar_min_citation_count=10)
        params = FilterTranslator.to_semantic_scholar(filters)
        assert params["minCitationCount"] == "10"

    def test_min_citation_count_zero_included(self):
        filters = SearchFilters(semanticscholar_min_citation_count=0)
        params = FilterTranslator.to_semantic_scholar(filters)
        assert params["minCitationCount"] == "0"

    def test_min_citation_count_none_omitted(self):
        params = FilterTranslator.to_semantic_scholar(SearchFilters())
        assert "minCitationCount" not in params

    def test_venues(self):
        filters = SearchFilters(semanticscholar_venues=["Nature", "NEJM"])
        params = FilterTranslator.to_semantic_scholar(filters)
        assert params["venue"] == "Nature,NEJM"

    def test_empty_filters_returns_empty_dict(self):
        filters = SearchFilters(europepmc_sources=[])  # avoid europepmc side effects
        params = FilterTranslator.to_semantic_scholar(filters)
        assert params == {}


# ---------------------------------------------------------------------------
# humanise_filters
# ---------------------------------------------------------------------------


class TestHumaniseFilters:
    def test_date_range_both_bounds(self):
        filters = SearchFilters(
            date_range=DateRange(start=date(2015, 1, 1), end=date(2024, 12, 31))
        )
        result = humanise_filters(filters, "pubmed")
        assert "Date: 2015" in result
        assert "2024" in result

    def test_date_range_no_start_shows_earliest(self):
        filters = SearchFilters(date_range=DateRange(end=date(2020, 1, 1)))
        result = humanise_filters(filters, "pubmed")
        assert "earliest" in result

    def test_date_range_no_end_shows_present(self):
        filters = SearchFilters(date_range=DateRange(start=date(2010, 1, 1)))
        result = humanise_filters(filters, "pubmed")
        assert "present" in result

    def test_languages_included(self):
        filters = SearchFilters(languages=["en", "fr"])
        result = humanise_filters(filters, "pubmed")
        assert "Language: en, fr" in result

    def test_publication_types_included(self):
        filters = SearchFilters(publication_types=["clinical_trial", "review"])
        result = humanise_filters(filters, "pubmed")
        assert "Publication types:" in result
        assert "clinical_trial" in result
        assert "review" in result

    def test_has_abstract_included(self):
        filters = SearchFilters(has_abstract=True)
        result = humanise_filters(filters, "pubmed")
        assert "Abstracts only" in result

    def test_pubmed_species_shown_for_pubmed_source(self):
        filters = SearchFilters(pubmed_species=["human", "animal"])
        result = humanise_filters(filters, "pubmed")
        assert "Species:" in result

    def test_pubmed_species_hidden_for_other_sources(self):
        filters = SearchFilters(pubmed_species=["human"])
        result = humanise_filters(filters, "europepmc")
        assert "Species" not in result

    def test_europepmc_open_access_shown_for_europepmc_source(self):
        filters = SearchFilters(europepmc_open_access=True)
        result = humanise_filters(filters, "europepmc")
        assert "Open access only" in result

    def test_europepmc_open_access_hidden_for_other_sources(self):
        filters = SearchFilters(europepmc_open_access=True)
        result = humanise_filters(filters, "pubmed")
        assert "Open access" not in result

    def test_semanticscholar_fields_shown_for_s2_source(self):
        filters = SearchFilters(semanticscholar_fields_of_study=["Medicine"])
        result = humanise_filters(filters, "semanticscholar")
        assert "Fields: Medicine" in result

    def test_semanticscholar_fields_hidden_for_other_sources(self):
        filters = SearchFilters(semanticscholar_fields_of_study=["Medicine"])
        result = humanise_filters(filters, "pubmed")
        assert "Fields" not in result

    def test_no_filters_returns_none_string(self):
        result = humanise_filters(SearchFilters(europepmc_sources=[]), "pubmed")
        assert result == "None"

    def test_parts_joined_with_semicolon(self):
        filters = SearchFilters(languages=["en"], has_abstract=True)
        result = humanise_filters(filters, "pubmed")
        assert "; " in result
