from services.query_builder import PICOInput, build_pubmed_query


def test_free_text_passthrough():
    pico = PICOInput(free_text='"Crohn disease"[MeSH] AND probiotic*[tiab]')
    result = build_pubmed_query(pico)
    assert result == '"Crohn disease"[MeSH] AND probiotic*[tiab]'


def test_single_component():
    pico = PICOInput(population="Crohn disease")
    result = build_pubmed_query(pico)
    assert '"Crohn disease"[tiab]' in result


def test_multiple_components_joined_with_and():
    pico = PICOInput(population="Crohn disease", intervention="probiotic")
    result = build_pubmed_query(pico)
    assert " AND " in result


def test_comma_separated_terms_joined_with_or():
    pico = PICOInput(population="Crohn disease, ulcerative colitis")
    result = build_pubmed_query(pico)
    assert " OR " in result


def test_empty_pico_returns_empty_string():
    pico = PICOInput()
    assert build_pubmed_query(pico) == ""
