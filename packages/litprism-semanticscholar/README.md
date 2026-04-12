# litprism-semanticscholar

Semantic Scholar search client for [LitPrism](https://litprism.org).

## Installation

```bash
pip install litprism-semanticscholar
```

## Quick start

```python
from litprism.semanticscholar import SemanticScholarClient

client = SemanticScholarClient(api_key="your-key")  # API key is optional
articles = client.search("CRISPR gene editing", max_results=100)

for article in articles:
    print(article.title, article.publication_year)
```

## Async usage

```python
from litprism.semanticscholar import AsyncSemanticScholarClient

async def main():
    client = AsyncSemanticScholarClient(api_key="your-key")
    async for batch in client.search_iter("cancer immunotherapy", max_results=500):
        for article in batch:
            print(article.title)
```

## API key

A Semantic Scholar API key raises the rate limit from ~1 req/s to 10 req/s.
Request a key at https://www.semanticscholar.org/product/api.
