from services.query_translator import QueryTranslator


def test_pubmed_passthrough():
    q = '"Crohn disease"[MeSH] AND probiotic*[tiab]'
    assert QueryTranslator.to_pubmed(q) == q


def test_mesh_converts_to_europepmc():
    q = '"Crohn disease"[MeSH] AND probiotic*[tiab]'
    result = QueryTranslator.to_europepmc(q)
    assert 'MESH:"Crohn disease"' in result
    assert "[MeSH]" not in result


def test_tiab_stripped_for_europepmc():
    result = QueryTranslator.to_europepmc("probiotic*[tiab]")
    assert "[tiab]" not in result
    assert "probiotic*" in result


def test_mesh_to_semantic_scholar():
    q = '"Crohn disease"[MeSH] AND probiotic*[tiab]'
    result = QueryTranslator.to_semantic_scholar(q)
    assert "[MeSH]" not in result
    assert '"Crohn disease"' in result
