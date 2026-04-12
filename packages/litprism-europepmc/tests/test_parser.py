"""Unit tests for litprism-europepmc JSON parser."""

import json
from datetime import date
from pathlib import Path

import pytest
from litprism.europepmc.exceptions import EuropePMCParseError
from litprism.europepmc.parser import parse_article, parse_results

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _single_result(name: str) -> dict:
    """Load a search fixture and return its first result dict."""
    data = _load(name)
    return data["resultList"]["result"][0]


# ---------------------------------------------------------------------------
# parse_article — happy path
# ---------------------------------------------------------------------------


class TestParseArticleHappyPath:
    def test_parses_id_and_pmid(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article is not None
        assert article.id == "33577785"
        assert article.pmid == "33577785"

    def test_parses_doi(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.doi == "10.1016/j.celrep.2021.108709"

    def test_parses_title(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert "Probiotic" in article.title

    def test_parses_abstract(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.abstract is not None
        assert "Background" in article.abstract

    def test_parses_journal(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.journal == "Cell Reports"

    def test_parses_publication_date(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.publication_date == date(2021, 2, 11)
        assert article.publication_year == 2021

    def test_parses_authors(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert len(article.authors) == 2
        assert article.authors[0].last_name == "Smith"
        assert article.authors[0].fore_name == "Jane"
        assert article.authors[0].affiliation == "University of Example"
        assert article.authors[1].last_name == "Jones"

    def test_parses_open_access_true(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.open_access is True

    def test_parses_mesh_terms(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert "Crohn Disease" in article.mesh_terms
        assert "Probiotics" in article.mesh_terms

    def test_parses_keywords(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert "probiotic" in article.keywords
        assert "Crohn disease" in article.keywords

    def test_parses_article_types(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert "Journal Article" in article.article_types
        assert "Randomized Controlled Trial" in article.article_types

    def test_parses_citation_count(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.citation_count == 42

    def test_parses_full_text_url(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.full_text_url is not None
        assert "doi.org" in article.full_text_url

    def test_source_literal_is_europepmc(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.source == "europepmc"

    def test_europepmc_source_field(self):
        raw = _single_result("search_single_result.json")
        article = parse_article(raw)
        assert article.europepmc_source == "MED"


# ---------------------------------------------------------------------------
# parse_article — ORCID and PDF URL
# ---------------------------------------------------------------------------


class TestParseArticleOrcidAndPdf:
    def test_parses_orcid(self):
        raw = _load("article_with_orcid.json")
        article = parse_article(raw)
        assert article is not None
        assert article.authors[0].orcid == "0000-0002-1234-5678"

    def test_no_orcid_when_absent(self):
        raw = _load("article_with_orcid.json")
        article = parse_article(raw)
        assert article.authors[1].orcid is None

    def test_parses_pdf_url(self):
        raw = _load("article_with_orcid.json")
        article = parse_article(raw)
        assert article.pdf_url == "https://example.org/article.pdf"

    def test_pub_type_string_coerced_to_list(self):
        """When pubType is a string (not list), it is still parsed correctly."""
        raw = _load("article_with_orcid.json")
        article = parse_article(raw)
        assert "Journal Article" in article.article_types

    def test_open_access_false_when_n(self):
        raw = _load("article_with_orcid.json")
        article = parse_article(raw)
        assert article.open_access is False


# ---------------------------------------------------------------------------
# parse_article — single-author / minimal metadata
# ---------------------------------------------------------------------------


class TestParseArticleSingleAuthor:
    def test_single_author_dict_parsed(self):
        """Europe PMC returns a dict (not list) for single-author articles."""
        raw = _load("article_single_author.json")
        article = parse_article(raw)
        assert article is not None
        assert len(article.authors) == 1
        assert article.authors[0].last_name == "Tanaka"

    def test_year_only_date_string(self):
        """firstPublicationDate may be just a year string."""
        raw = _load("article_single_author.json")
        article = parse_article(raw)
        assert article.publication_date is None
        assert article.publication_year == 2023

    def test_null_abstract_becomes_none(self):
        raw = _load("article_single_author.json")
        article = parse_article(raw)
        assert article.abstract is None

    def test_empty_keyword_list(self):
        raw = _load("article_single_author.json")
        article = parse_article(raw)
        assert article.keywords == []

    def test_empty_mesh_list(self):
        raw = _load("article_single_author.json")
        article = parse_article(raw)
        assert article.mesh_terms == []

    def test_preprint_source(self):
        raw = _load("article_single_author.json")
        article = parse_article(raw)
        assert article.europepmc_source == "PPR"

    def test_zero_citation_count_becomes_none(self):
        """citedByCount=0 is treated as unknown (None), not 0."""
        raw = _load("article_single_author.json")
        article = parse_article(raw)
        assert article.citation_count is None


# ---------------------------------------------------------------------------
# parse_article — invalid / missing required fields
# ---------------------------------------------------------------------------


class TestParseArticleInvalid:
    def test_missing_id_returns_none(self):
        assert parse_article({}) is None

    def test_missing_title_returns_none(self):
        assert parse_article({"id": "123", "title": ""}) is None

    def test_empty_dict_returns_none(self):
        assert parse_article({}) is None


# ---------------------------------------------------------------------------
# parse_results
# ---------------------------------------------------------------------------


class TestParseResults:
    def test_parses_list_of_results(self):
        data = _load("search_single_result.json")
        raw_results = data["resultList"]["result"]
        articles = parse_results(raw_results)
        assert len(articles) == 1
        assert articles[0].pmid == "33577785"

    def test_empty_list_returns_empty(self):
        assert parse_results([]) == []

    def test_skips_malformed_records(self):
        """Malformed records (missing id/title) are silently skipped."""
        raw = [
            {"id": "123", "title": "Valid article"},
            {"id": "", "title": "No id"},
            {},
        ]
        articles = parse_results(raw)
        assert len(articles) == 1
        assert articles[0].id == "123"

    def test_non_list_raises_parse_error(self):
        with pytest.raises(EuropePMCParseError):
            parse_results({"result": []})  # type: ignore[arg-type]
