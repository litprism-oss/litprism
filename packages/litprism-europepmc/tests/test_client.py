"""Unit tests for litprism-europepmc client (httpx mocked)."""

from litprism.europepmc.client import AsyncEuropePMCClient
from litprism.europepmc.models import SearchFilters


class TestAsyncEuropePMCClientInit:
    def test_default_init(self):
        client = AsyncEuropePMCClient()
        assert client._api_key is None
        assert client._email is None

    def test_init_with_credentials(self):
        client = AsyncEuropePMCClient(api_key="key123", email="test@example.com")
        assert client._api_key == "key123"
        assert client._email == "test@example.com"


class TestBuildQuery:
    def test_no_filters_returns_query_unchanged(self):
        client = AsyncEuropePMCClient()
        result = client._build_query("cancer prognosis", None)
        assert result == "cancer prognosis"

    def test_filters_appended_as_and(self):
        client = AsyncEuropePMCClient()
        filters = SearchFilters(has_abstract=True, europepmc_sources=[])
        result = client._build_query("cancer", filters)
        assert result.startswith("(cancer) AND")
        assert "HAS_ABSTRACT:Y" in result

    def test_empty_filter_query_returns_base_query(self):
        client = AsyncEuropePMCClient()
        # SearchFilters with no active filters (but must suppress default MED source)
        filters = SearchFilters(europepmc_sources=[], europepmc_mesh_synonyms=True)
        result = client._build_query("cancer", filters)
        assert result == "cancer"
