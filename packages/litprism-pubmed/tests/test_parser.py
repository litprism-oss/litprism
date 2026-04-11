"""Tests for litprism.pubmed.parser."""

from datetime import date
from pathlib import Path

import pytest
from litprism.pubmed.exceptions import PubMedParseError
from litprism.pubmed.parser import parse_xml

FIXTURES = Path(__file__).parent / "fixtures"


def load(filename: str) -> str:
    return (FIXTURES / filename).read_text()


class TestParseSingleArticle:
    def test_pmid(self):
        articles = parse_xml(load("single_article.xml"))
        assert len(articles) == 1
        assert articles[0].pmid == "12345678"
        assert articles[0].id == "12345678"

    def test_title(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert "Probiotic" in article.title
        assert "Crohn" in article.title

    def test_abstract(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert article.abstract is not None
        assert "microbiome" in article.abstract
        assert "placebo" in article.abstract

    def test_authors(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert len(article.authors) == 2
        assert article.authors[0].last_name == "Smith"
        assert article.authors[0].fore_name == "Jane"
        assert article.authors[0].orcid == "0000-0001-2345-6789"
        assert "London" in (article.authors[0].affiliation or "")
        assert article.authors[1].last_name == "Jones"

    def test_journal(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert article.journal == "Journal of Crohn's and Colitis"

    def test_publication_date(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert article.publication_date == date(2021, 3, 15)
        assert article.publication_year == 2021

    def test_doi(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert article.doi == "10.1093/ecco-jcc/jjab001"

    def test_mesh_terms(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert "Crohn Disease" in article.mesh_terms
        assert "Probiotics" in article.mesh_terms

    def test_article_types(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert "Randomized Controlled Trial" in article.article_types

    def test_open_access_via_pmc(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert article.open_access is True
        assert "PMC7654321" in (article.full_text_url or "")

    def test_source(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert article.source == "pubmed"

    def test_upload_format_is_none(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert article.upload_format is None


class TestParseBatchArticles:
    def test_count(self):
        articles = parse_xml(load("batch_articles.xml"))
        assert len(articles) == 3

    def test_pmids(self):
        articles = parse_xml(load("batch_articles.xml"))
        pmids = {a.pmid for a in articles}
        assert pmids == {"11111111", "22222222", "33333333"}

    def test_doi_present_on_second(self):
        articles = parse_xml(load("batch_articles.xml"))
        by_pmid = {a.pmid: a for a in articles}
        assert by_pmid["22222222"].doi == "10.1016/S0140-6736(21)00001-1"
        assert by_pmid["11111111"].doi is None

    def test_article_types_multiple(self):
        articles = parse_xml(load("batch_articles.xml"))
        by_pmid = {a.pmid: a for a in articles}
        assert "Review" in by_pmid["33333333"].article_types


class TestMissingAbstract:
    def test_abstract_is_none(self):
        articles = parse_xml(load("missing_abstract.xml"))
        assert len(articles) == 1
        assert articles[0].abstract is None

    def test_medline_date_parsed(self):
        article = parse_xml(load("missing_abstract.xml"))[0]
        assert article.publication_year == 2019

    def test_initials_used_as_fore_name(self):
        article = parse_xml(load("missing_abstract.xml"))[0]
        assert article.authors[0].fore_name == "J"

    def test_not_open_access(self):
        article = parse_xml(load("missing_abstract.xml"))[0]
        assert article.open_access is False


class TestMalformedXml:
    def test_raises_parse_error(self):
        with pytest.raises(PubMedParseError):
            parse_xml("this is not xml <<<")

    def test_empty_set_returns_empty_list(self):
        xml = '<?xml version="1.0"?><PubmedArticleSet></PubmedArticleSet>'
        assert parse_xml(xml) == []
