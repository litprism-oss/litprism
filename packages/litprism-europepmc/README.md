# litprism-europepmc

Europe PMC search client for LitPrism.

Wraps the Europe PMC REST API with rate limiting, cursor-based pagination, and
normalised output to the shared `Article` model.

## Install

```bash
pip install litprism-europepmc
```

## Usage

```python
from litprism.europepmc import EuropePMCClient

client = EuropePMCClient()

articles = client.search(
    query='("Crohn disease") AND probiotic',
    max_results=500,
)
```

## Rate limits

- Without API key: 3 requests/second
- With API key: 10 requests/second
