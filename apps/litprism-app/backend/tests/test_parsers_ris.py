"""RIS parser tests — title, DOI, abstract, no PMID for Scopus, multiple authors."""

from pathlib import Path

from services.parsers.ris import parse


def _load(path: str) -> bytes:
    return Path(path).read_bytes()


def test_ris_parses_title(scopus_ris_path):
    records = parse(_load(scopus_ris_path), "scopus_export.ris")
    assert len(records) == 1
    assert "Iron" in records[0].title


def test_ris_parses_doi(scopus_ris_path):
    records = parse(_load(scopus_ris_path), "scopus_export.ris")
    assert records[0].doi == "10.1016/j.clnesp.2020.09.027"


def test_ris_parses_abstract(scopus_ris_path):
    records = parse(_load(scopus_ris_path), "scopus_export.ris")
    assert records[0].abstract is not None
    assert "Iron deficiency" in records[0].abstract


def test_ris_no_pmid_for_scopus(scopus_ris_path):
    """Scopus RIS exports have no PMID field."""
    records = parse(_load(scopus_ris_path), "scopus_export.ris")
    assert records[0].pmid is None


def test_ris_parses_multiple_authors(scopus_ris_path):
    records = parse(_load(scopus_ris_path), "scopus_export.ris")
    assert len(records[0].authors) == 2
