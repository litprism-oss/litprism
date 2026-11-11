from services.filter_translator import translate_for_source


def test_pubmed_date_range():
    params = translate_for_source(
        {"date_range": {"start": "2020-01-01", "end": "2024-12-31"}}, "pubmed"
    )
    assert params["mindate"] == "2020/01/01"
    assert params["maxdate"] == "2024/12/31"


def test_europepmc_language():
    params = translate_for_source({"languages": ["en"]}, "europepmc")
    assert "LANG:en" in params.get("filter_query", "")


def test_semantic_scholar_year():
    params = translate_for_source(
        {"date_range": {"start": "2020-01-01", "end": "2024-12-31"}}, "semanticscholar"
    )
    assert params["publicationDateOrYear"] == "2020-01-01:2024-12-31"


def test_unknown_source_returns_empty():
    params = translate_for_source({"languages": ["en"]}, "unknown_source")
    assert params == {}


def test_none_filters_returns_empty():
    assert translate_for_source(None, "pubmed") == {}
