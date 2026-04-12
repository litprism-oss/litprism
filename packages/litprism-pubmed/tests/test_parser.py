"""Tests for litprism.pubmed.parser — no network calls, fixture XML only."""

from datetime import date
from pathlib import Path

import pytest
from litprism.pubmed.exceptions import PubMedParseError
from litprism.pubmed.parser import parse_xml

FIXTURES = Path(__file__).parent / "fixtures"


def load(filename: str) -> str:
    return (FIXTURES / filename).read_text()


# ---------------------------------------------------------------------------
# single_article.xml — full-field article
# ---------------------------------------------------------------------------


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

    def test_abstract_sections_concatenated(self):
        """Multi-section abstract elements are joined with a space."""
        article = parse_xml(load("single_article.xml"))[0]
        # single_article.xml has 4 AbstractText sections
        assert "Background" in article.abstract
        assert "METHODS" in article.abstract or "probiotic supplementation" in article.abstract
        assert "CONCLUSIONS" in article.abstract or "benefit" in article.abstract

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

    def test_pdf_path_is_none(self):
        article = parse_xml(load("single_article.xml"))[0]
        assert article.pdf_path is None

    def test_citation_count_is_none(self):
        """citation_count is not available from PubMed XML."""
        article = parse_xml(load("single_article.xml"))[0]
        assert article.citation_count is None


# ---------------------------------------------------------------------------
# batch_articles.xml — three articles, varied DOI/type coverage
# ---------------------------------------------------------------------------


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

    def test_open_access_false_without_pmc(self):
        articles = parse_xml(load("batch_articles.xml"))
        by_pmid = {a.pmid: a for a in articles}
        # None of the batch articles have a PMC ID
        assert by_pmid["11111111"].open_access is False
        assert by_pmid["22222222"].open_access is False

    def test_publication_years(self):
        articles = parse_xml(load("batch_articles.xml"))
        by_pmid = {a.pmid: a for a in articles}
        assert by_pmid["11111111"].publication_year == 2020
        assert by_pmid["22222222"].publication_year == 2021
        assert by_pmid["33333333"].publication_year == 2022


# ---------------------------------------------------------------------------
# missing_abstract.xml — letter with MedlineDate and Initials-only author
# ---------------------------------------------------------------------------


class TestMissingAbstract:
    def test_abstract_is_none(self):
        articles = parse_xml(load("missing_abstract.xml"))
        assert len(articles) == 1
        assert articles[0].abstract is None

    def test_medline_date_parsed(self):
        article = parse_xml(load("missing_abstract.xml"))[0]
        assert article.publication_year == 2019

    def test_initials_used_as_fore_name(self):
        """When ForeName is absent, Initials are used as fore_name."""
        article = parse_xml(load("missing_abstract.xml"))[0]
        assert article.authors[0].fore_name == "J"

    def test_not_open_access(self):
        article = parse_xml(load("missing_abstract.xml"))[0]
        assert article.open_access is False

    def test_article_type_letter(self):
        article = parse_xml(load("missing_abstract.xml"))[0]
        assert "Letter" in article.article_types


# ---------------------------------------------------------------------------
# malformed_date.xml — unparseable MedlineDate ("Spring 2020")
# ---------------------------------------------------------------------------


class TestMalformedDate:
    def test_article_is_still_returned(self):
        """A bad date must not cause the article to be dropped."""
        articles = parse_xml(load("malformed_date.xml"))
        assert len(articles) == 1
        assert articles[0].pmid == "55555555"

    def test_publication_date_is_none(self):
        article = parse_xml(load("malformed_date.xml"))[0]
        assert article.publication_date is None

    def test_publication_year_is_none(self):
        """'Spring 2020' does not start with a 4-digit year — year is None."""
        article = parse_xml(load("malformed_date.xml"))[0]
        assert article.publication_year is None

    def test_title_and_abstract_still_parsed(self):
        article = parse_xml(load("malformed_date.xml"))[0]
        assert "vitamin d" in article.title.lower()
        assert article.abstract is not None


# ---------------------------------------------------------------------------
# Keywords — inline XML, no fixture file needed
# ---------------------------------------------------------------------------


class TestKeywords:
    _XML_WITH_KEYWORDS = """\
<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>77777777</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue>
          <Title>Test Journal</Title>
        </Journal>
        <ArticleTitle>Article with keywords.</ArticleTitle>
        <Abstract><AbstractText>Some abstract text.</AbstractText></Abstract>
        <AuthorList>
          <Author><LastName>Author</LastName><ForeName>Test</ForeName></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
        </PublicationTypeList>
      </Article>
      <KeywordList Owner="NOTNLM">
        <Keyword MajorTopicYN="N">gut microbiome</Keyword>
        <Keyword MajorTopicYN="N">inflammation</Keyword>
        <Keyword MajorTopicYN="Y">probiotic</Keyword>
      </KeywordList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">77777777</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""

    def test_keywords_parsed(self):
        articles = parse_xml(self._XML_WITH_KEYWORDS)
        assert len(articles) == 1
        assert "gut microbiome" in articles[0].keywords
        assert "inflammation" in articles[0].keywords
        assert "probiotic" in articles[0].keywords

    def test_keywords_count(self):
        articles = parse_xml(self._XML_WITH_KEYWORDS)
        assert len(articles[0].keywords) == 3


# ---------------------------------------------------------------------------
# Malformed / edge-case XML
# ---------------------------------------------------------------------------


class TestMalformedXml:
    def test_raises_parse_error(self):
        with pytest.raises(PubMedParseError):
            parse_xml("this is not xml <<<")

    def test_empty_set_returns_empty_list(self):
        xml = '<?xml version="1.0"?><PubmedArticleSet></PubmedArticleSet>'
        assert parse_xml(xml) == []

    def test_article_without_pmid_is_skipped(self):
        """parse_article returns None for articles with no PMID."""
        xml = """\
<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue>
          <Title>Some Journal</Title>
        </Journal>
        <ArticleTitle>No PMID article.</ArticleTitle>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData><ArticleIdList/></PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""
        assert parse_xml(xml) == []

    def test_multiple_articles_one_malformed(self):
        """A malformed article is skipped; valid ones are returned."""
        xml = """\
<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>88888888</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2022</Year></PubDate></JournalIssue>
          <Title>Good Journal</Title>
        </Journal>
        <ArticleTitle>Valid article.</ArticleTitle>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">88888888</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <!-- No MedlineCitation at all — parse_article returns None -->
  </PubmedArticle>
</PubmedArticleSet>"""
        articles = parse_xml(xml)
        assert len(articles) == 1
        assert articles[0].pmid == "88888888"
