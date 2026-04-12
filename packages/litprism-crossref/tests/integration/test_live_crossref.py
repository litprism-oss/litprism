"""Integration tests for AsyncCrossrefClient — hits the real Crossref API.

Run with:
    uv run pytest packages/litprism-crossref/tests/integration/ -v -m integration
"""

import pytest
from litprism.crossref.client import AsyncCrossrefClient
from litprism.crossref.models import CrossrefMetadata

# A stable, well-known DOI that is unlikely to be removed from Crossref.
_KNOWN_DOI = "10.1038/s41586-021-03819-2"  # AlphaFold paper, Nature 2021


@pytest.mark.integration
async def test_enrich_alphafold_doi() -> None:
    client = AsyncCrossrefClient(mailto="integration-test@litprism.org")
    meta = await client.enrich_by_doi(_KNOWN_DOI)

    assert isinstance(meta, CrossrefMetadata)
    assert meta.doi == _KNOWN_DOI
    assert meta.title is not None
    assert "AlphaFold" in meta.title
    assert meta.publication_year == 2021
    assert meta.journal is not None
    assert meta.citation_count is not None and meta.citation_count > 0
    assert len(meta.authors) > 0


@pytest.mark.integration
async def test_enrich_doi_with_prefix() -> None:
    client = AsyncCrossrefClient(mailto="integration-test@litprism.org")
    meta = await client.enrich_by_doi(f"https://doi.org/{_KNOWN_DOI}")
    assert meta.doi == _KNOWN_DOI
