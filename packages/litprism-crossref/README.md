# litprism-crossref

Crossref DOI enrichment client for [LitPrism](https://litprism.org).

Fetches rich metadata for a single article by DOI from the
[Crossref REST API](https://api.crossref.org/).

## Installation

```bash
pip install litprism-crossref
```

## Usage

```python
from litprism.crossref import CrossrefClient

client = CrossrefClient(mailto="you@example.com")
meta = client.enrich_by_doi("10.1038/s41586-021-03819-2")
print(meta.title)
print(meta.citation_count)
```

## API key

No API key is required. Supplying a `mailto=` email address opts you into
Crossref's **polite pool**, which provides higher rate limits and better
reliability. Always set it.
