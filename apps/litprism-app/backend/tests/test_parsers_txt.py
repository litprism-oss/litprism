"""Txt parser tests — PubMed Summary format detection and parsing, MEDLINE routing."""

from pathlib import Path

from services.parsers.nbib import parse as parse_nbib
from services.parsers.txt import is_pubmed_summary_txt
from services.parsers.txt import parse as parse_summary_txt


def _load(path: str) -> bytes:
    return Path(path).read_bytes()


def test_summary_txt_parses_two_records(pubmed_summary_txt_path):
    records = parse_summary_txt(_load(pubmed_summary_txt_path), "pubmed_summary.txt")
    assert len(records) == 2


def test_summary_txt_extracts_pmid(pubmed_summary_txt_path):
    records = parse_summary_txt(_load(pubmed_summary_txt_path), "pubmed_summary.txt")
    assert records[0].pmid == "31009449"


def test_summary_txt_extracts_doi(pubmed_summary_txt_path):
    records = parse_summary_txt(_load(pubmed_summary_txt_path), "pubmed_summary.txt")
    assert records[0].doi == "10.1234/test"


def test_summary_txt_abstract_is_none(pubmed_summary_txt_path):
    """Summary format has no abstract."""
    records = parse_summary_txt(_load(pubmed_summary_txt_path), "pubmed_summary.txt")
    assert records[0].abstract is None


def test_summary_txt_detection(pubmed_summary_txt_path, pubmed_medline_txt_path):
    assert is_pubmed_summary_txt(_load(pubmed_summary_txt_path)) is True
    assert is_pubmed_summary_txt(_load(pubmed_medline_txt_path)) is False


def test_medline_txt_parsed_by_nbib_parser(pubmed_medline_txt_path):
    """MEDLINE .txt (PMID- prefix) is parsed by the nbib parser."""
    records = parse_nbib(_load(pubmed_medline_txt_path), "pubmed_medline.txt")
    assert len(records) == 1
    assert records[0].pmid == "31009449"
    assert records[0].abstract is not None
