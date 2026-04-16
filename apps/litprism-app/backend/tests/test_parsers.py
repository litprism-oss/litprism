from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from services.parsers import ParsedArticle
from services.parsers.bibtex import parse as parse_bib
from services.parsers.csv_xlsx import parse as parse_csv
from services.parsers.nbib import parse as parse_nbib
from services.parsers.pdf import _extract_doi, _heuristic_title
from services.parsers.pdf import parse as parse_pdf
from services.parsers.ris import parse as parse_ris

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# NBIB
# ---------------------------------------------------------------------------


def test_nbib_parses_title():
    content = (FIXTURES / "sample.nbib").read_bytes()
    articles = parse_nbib(content, "sample.nbib")
    assert len(articles) == 3
    assert all(a.title for a in articles)


def test_nbib_parses_pmid():
    content = (FIXTURES / "sample.nbib").read_bytes()
    articles = parse_nbib(content, "sample.nbib")
    assert any(a.pmid for a in articles)


def test_nbib_parses_doi():
    content = (FIXTURES / "sample.nbib").read_bytes()
    articles = parse_nbib(content, "sample.nbib")
    assert any(a.doi for a in articles)


def test_nbib_parses_mesh_terms():
    content = (FIXTURES / "sample.nbib").read_bytes()
    articles = parse_nbib(content, "sample.nbib")
    first = articles[0]
    assert len(first.mesh_terms) > 0
    # Trailing * markers should be stripped
    assert all(not t.endswith("*") for t in first.mesh_terms)


def test_nbib_parses_authors():
    content = (FIXTURES / "sample.nbib").read_bytes()
    articles = parse_nbib(content, "sample.nbib")
    first = articles[0]
    assert len(first.authors) == 2
    assert first.authors[0]["last_name"] == "Smith"


# ---------------------------------------------------------------------------
# RIS
# ---------------------------------------------------------------------------


def test_ris_parses_three_records():
    content = (FIXTURES / "sample.ris").read_bytes()
    articles = parse_ris(content, "sample.ris")
    assert len(articles) == 3


def test_ris_parses_title():
    content = (FIXTURES / "sample.ris").read_bytes()
    articles = parse_ris(content, "sample.ris")
    assert all(a.title for a in articles)


def test_ris_parses_doi():
    content = (FIXTURES / "sample.ris").read_bytes()
    articles = parse_ris(content, "sample.ris")
    assert any(a.doi for a in articles)


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------


def test_bib_parses_three_records():
    content = (FIXTURES / "sample.bib").read_bytes()
    articles = parse_bib(content, "sample.bib")
    assert len(articles) == 3


def test_bib_parses_title():
    content = (FIXTURES / "sample.bib").read_bytes()
    articles = parse_bib(content, "sample.bib")
    assert all(a.title for a in articles)


def test_bib_parses_doi():
    content = (FIXTURES / "sample.bib").read_bytes()
    articles = parse_bib(content, "sample.bib")
    assert all(a.doi for a in articles)


def test_bib_parses_authors():
    content = (FIXTURES / "sample.bib").read_bytes()
    articles = parse_bib(content, "sample.bib")
    assert all(len(a.authors) > 0 for a in articles)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_parses_scopus_columns():
    csv_content = b"Title,Abstract,Authors,DOI\nTest Article,An abstract,Smith J,10.1234/test\n"
    articles = parse_csv(csv_content, "test.csv")
    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].doi == "10.1234/test"


def test_csv_parses_multiple_rows():
    csv_content = (
        b"Title,Abstract,DOI\n"
        b"Article One,Abstract one,10.1234/one\n"
        b"Article Two,Abstract two,10.1234/two\n"
    )
    articles = parse_csv(csv_content, "test.csv")
    assert len(articles) == 2


def test_csv_skips_rows_without_title():
    csv_content = b"Title,Abstract\n,An abstract with no title\n"
    articles = parse_csv(csv_content, "test.csv")
    assert len(articles) == 0


def test_csv_case_insensitive_headers():
    csv_content = b"TITLE,ABSTRACT\nMy Article,My abstract\n"
    articles = parse_csv(csv_content, "test.csv")
    assert len(articles) == 1
    assert articles[0].title == "My Article"


# ---------------------------------------------------------------------------
# PDF — unit tests (no real PDF file; fitz builds minimal in-memory PDFs)
# ---------------------------------------------------------------------------


def test_extract_doi_from_text():
    text = "Published online: https://doi.org/10.1234/abcd.2024 some other text"
    assert _extract_doi(text) == "10.1234/abcd.2024"


def test_extract_doi_none_when_absent():
    assert _extract_doi("No DOI here, just regular text") is None


def test_extract_doi_strips_trailing_punctuation():
    assert _extract_doi("See doi: 10.1234/test.2024.") == "10.1234/test.2024"


def test_heuristic_title_skips_journal_header():
    text = "Volume 12, Issue 3, 2024\nEffects of Probiotics in Crohn Disease\nAbstract"
    title = _heuristic_title(text, "article.pdf")
    assert "Effects of Probiotics" in title


def test_heuristic_title_falls_back_to_filename():
    title = _heuristic_title("", "my_paper_2024.pdf")
    assert title == "my_paper_2024"


def test_pdf_uses_crossref_when_doi_found():
    """When DOI is found, Crossref lookup is called and its result is returned."""
    import fitz

    fake_article = ParsedArticle(
        title="Authoritative Title from Crossref",
        upload_format="pdf",
        doi="10.1234/test",
    )
    with patch("services.parsers.pdf._crossref_lookup", new=AsyncMock(return_value=fake_article)):
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "doi: 10.1234/test")
        content = doc.tobytes()
        articles = parse_pdf(content, "test.pdf")
    assert articles[0].title == "Authoritative Title from Crossref"


def test_pdf_falls_back_to_heuristic_when_no_doi():
    """When no DOI found, heuristic title extraction is used."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Effects of Probiotics on Gut Microbiome")
    page.insert_text((50, 80), "Abstract\nThis study investigated...")
    content = doc.tobytes()
    with patch("services.parsers.pdf._crossref_lookup", new=AsyncMock(return_value=None)):
        articles = parse_pdf(content, "test.pdf")
    assert articles[0].title != ""
    assert articles[0].doi is None


def test_pdf_raises_on_password_protected():
    import fitz
    from services.parsers.exceptions import PasswordProtectedPDFError

    doc = fitz.open()
    doc.new_page()
    content = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="secret",
        owner_pw="owner",
    )
    with pytest.raises(PasswordProtectedPDFError):
        parse_pdf(content, "locked.pdf")


def test_pdf_raises_on_empty_text_layer():
    """A PDF with pages but no extractable text — e.g. scanned image-only document."""
    import fitz
    from services.parsers.exceptions import EmptyFileError

    doc = fitz.open()
    doc.new_page()  # blank page — no text inserted
    content = doc.tobytes()
    with (
        patch("services.parsers.pdf._crossref_lookup", new=AsyncMock(return_value=None)),
        pytest.raises(EmptyFileError),
    ):
        parse_pdf(content, "scanned.pdf")
