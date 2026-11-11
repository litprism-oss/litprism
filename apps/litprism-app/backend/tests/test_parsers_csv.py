"""PubMed CSV parser tests — BOM, column mapping, author splitting, empty DOI."""

from pathlib import Path

from services.parsers.csv_xlsx import parse


def _load(path: str) -> bytes:
    return Path(path).read_bytes()


def test_pubmed_csv_strips_bom(pubmed_csv_path):
    records = parse(_load(pubmed_csv_path), "pubmed_export.csv")
    assert len(records) == 2


def test_pubmed_csv_maps_pmid(pubmed_csv_path):
    records = parse(_load(pubmed_csv_path), "pubmed_export.csv")
    assert records[0].pmid == "31009449"


def test_pubmed_csv_maps_title(pubmed_csv_path):
    records = parse(_load(pubmed_csv_path), "pubmed_export.csv")
    assert "Probiotic" in records[0].title


def test_pubmed_csv_maps_doi(pubmed_csv_path):
    records = parse(_load(pubmed_csv_path), "pubmed_export.csv")
    assert records[0].doi == "10.1234/test"


def test_pubmed_csv_abstract_is_none(pubmed_csv_path):
    """PubMed CSV has no abstract column — must be None, not empty string."""
    records = parse(_load(pubmed_csv_path), "pubmed_export.csv")
    assert records[0].abstract is None


def test_pubmed_csv_splits_authors(pubmed_csv_path):
    """Author string 'Smith J' split into list of dicts with last_name."""
    records = parse(_load(pubmed_csv_path), "pubmed_export.csv")
    authors = records[0].authors
    assert isinstance(authors, list)
    assert len(authors) >= 1
    assert authors[0]["last_name"] == "Smith"


def test_pubmed_csv_handles_empty_doi(pubmed_csv_path):
    """Empty DOI cell should become None, not empty string."""
    records = parse(_load(pubmed_csv_path), "pubmed_export.csv")
    assert records[1].doi is None


def test_pubmed_csv_detection_via_columns(pubmed_csv_path, tmp_path):
    """PubMed CSV is detected by column headers; generic CSV is not."""
    import csv
    import io

    from services.parsers.csv_xlsx import _is_pubmed_csv

    # PubMed CSV
    text = Path(pubmed_csv_path).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    assert _is_pubmed_csv(list(reader.fieldnames)) is True

    # Generic CSV
    generic_content = b"name,value\nfoo,bar\n"
    reader2 = csv.DictReader(io.StringIO(generic_content.decode()))
    assert _is_pubmed_csv(list(reader2.fieldnames)) is False
