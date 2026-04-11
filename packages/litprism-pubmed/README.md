# litprism-pubmed

PubMed / MEDLINE search client for LitPrism.

Wraps the NCBI E-utilities API with rate limiting, batch fetching, and
optional SQLite caching. Normalises results to the shared `Article` model.

## Install

```bash
pip install litprism-pubmed
```

## Usage

```python
from litprism.pubmed import PubMedClient

client = PubMedClient(api_key="...")  # api_key is optional

result = client.search(
    query='("Crohn disease"[MeSH]) AND probiotic*[tiab]',
    max_results=500,
    date_range=("2015-01-01", "2024-12-31"),
)
articles = client.fetch(result.pmids)
```

## Rate limits

- Without API key: 3 requests/second
- With API key: 10 requests/second

Get a free NCBI API key at https://www.ncbi.nlm.nih.gov/account/
