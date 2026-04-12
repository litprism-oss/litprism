"""Unit tests for litprism-semanticscholar JSON parser."""

import json
from pathlib import Path

import pytest
from litprism.semanticscholar.exceptions import SemanticScholarParseError
from litprism.semanticscholar.parser import parse_article, parse_results

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestParseArticle:
    def test_parses_full_record(self):
        raw = _load("search_single_result.json")
        article = parse_article(raw["data"][0])
        assert article is not None
        assert article.id == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        assert article.pmid == "33577785"
        assert article.doi == "10.1016/j.celrep.2021.108709"
        expected_title = "CRISPR-Cas9 gene editing for sickle cell disease and beta-thalassaemia"
        assert article.title == expected_title
        assert article.source == "semanticscholar"

    def test_parses_publication_date(self):
        raw = _load("search_single_result.json")
        article = parse_article(raw["data"][0])
        assert article is not None
        assert article.publication_year == 2021
        assert article.publication_date is not None
        assert article.publication_date.isoformat() == "2021-01-21"

    def test_parses_authors(self):
        raw = _load("search_single_result.json")
        article = parse_article(raw["data"][0])
        assert article is not None
        assert len(article.authors) == 2
        assert article.authors[0].last_name == "Doudna"
        assert article.authors[0].fore_name == "Jennifer"

    def test_parses_open_access(self):
        raw = _load("search_single_result.json")
        article = parse_article(raw["data"][0])
        assert article is not None
        assert article.open_access is True
        assert article.pdf_url == "https://example.com/paper.pdf"

    def test_parses_fields_of_study(self):
        raw = _load("search_single_result.json")
        article = parse_article(raw["data"][0])
        assert article is not None
        assert "Medicine" in article.fields_of_study
        assert "Biology" in article.fields_of_study

    def test_parses_citation_count(self):
        raw = _load("search_single_result.json")
        article = parse_article(raw["data"][0])
        assert article is not None
        assert article.citation_count == 512

    def test_parses_venue(self):
        raw = _load("search_single_result.json")
        article = parse_article(raw["data"][0])
        assert article is not None
        assert article.venue == "New England Journal of Medicine"

    def test_null_open_access_pdf(self):
        raw = _load("search_page2.json")
        article = parse_article(raw["data"][0])
        assert article is not None
        assert article.open_access is False
        assert article.pdf_url is None

    def test_missing_paper_id_returns_none(self):
        article = parse_article({"title": "Some title"})
        assert article is None

    def test_missing_title_returns_none(self):
        article = parse_article({"paperId": "abc123"})
        assert article is None

    def test_author_single_word_name(self):
        """A single-word author name goes to last_name with fore_name=None."""
        raw = {
            "paperId": "abc123",
            "title": "Test",
            "authors": [{"authorId": "1", "name": "Mononym"}],
        }
        article = parse_article(raw)
        assert article is not None
        assert article.authors[0].last_name == "Mononym"
        assert article.authors[0].fore_name is None

    def test_year_fallback_when_no_date(self):
        """year field used when publicationDate is absent."""
        raw = {
            "paperId": "abc123",
            "title": "Test",
            "year": 2019,
        }
        article = parse_article(raw)
        assert article is not None
        assert article.publication_year == 2019
        assert article.publication_date is None


class TestParseResults:
    def test_parses_list(self):
        raw = _load("search_single_result.json")
        articles = parse_results(raw["data"])
        assert len(articles) == 1

    def test_empty_list_returns_empty(self):
        assert parse_results([]) == []

    def test_skips_malformed_records(self):
        results = [{"no_paperId": True}, {"paperId": "abc", "title": "Good"}]
        articles = parse_results(results)
        assert len(articles) == 1

    def test_non_list_raises(self):
        with pytest.raises(SemanticScholarParseError):
            parse_results({"data": []})  # type: ignore[arg-type]
