"""NBIB parser tests — PMID, abstract, FAU preference, DOI extraction."""

from pathlib import Path

from services.parsers.nbib import parse


def _load(path: str) -> bytes:
    return Path(path).read_bytes()


def test_nbib_parses_pmid(pubmed_nbib_path):
    records = parse(_load(pubmed_nbib_path), "pubmed.nbib")
    assert records[0].pmid == "31009449"


def test_nbib_parses_abstract(pubmed_nbib_path):
    records = parse(_load(pubmed_nbib_path), "pubmed.nbib")
    assert records[0].abstract is not None
    assert "Probiotics" in records[0].abstract


def test_nbib_prefers_fau_over_au(pubmed_nbib_path):
    """FAU (full author name) should be used over AU (initials) when present."""
    records = parse(_load(pubmed_nbib_path), "pubmed.nbib")
    authors = records[0].authors
    assert any("Smith" in a["last_name"] for a in authors)
    # FAU gives fore_name with full name, not just initials
    smith = next(a for a in authors if a["last_name"] == "Smith")
    assert "John" in smith["fore_name"]


def test_nbib_parses_doi(pubmed_nbib_path):
    records = parse(_load(pubmed_nbib_path), "pubmed.nbib")
    assert records[0].doi == "10.1234/test"
