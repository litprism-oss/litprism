from litprism.europepmc.filters import FilterTranslator as EuropePMCFT
from litprism.europepmc.models import SearchFilters as EuropePMCFilters
from litprism.pubmed.filters import FilterTranslator as PubMedFT
from litprism.pubmed.models import SearchFilters as PubMedFilters
from litprism.semanticscholar.filters import FilterTranslator as S2FT
from litprism.semanticscholar.models import SearchFilters as S2Filters


def translate_for_source(filters_dict: dict | None, source: str) -> dict:
    """Deserialise stored filters and return source-specific API params."""
    if not filters_dict:
        return {}
    if source == "pubmed":
        return PubMedFT.to_pubmed(PubMedFilters(**filters_dict))
    if source == "europepmc":
        return EuropePMCFT.to_europepmc(EuropePMCFilters(**filters_dict))
    if source == "semanticscholar":
        return S2FT.to_semanticscholar(S2Filters(**filters_dict))
    return {}
