# LitPrism

Open-source search, screening, and audit layer for evidence synthesis.

LitPrism automates the multi-database search step that every existing systematic review tool
skips — then screens with an LLM and exports a clean, auditable set ready for any downstream
tool or journal submission.

```
Natural language / PICO / direct query
              ↓
   LitPrism: Search → Dedup → Screen
   + PRISMA-S compliant search record
              ↓
  .nbib / .ris / .csv / ASReview format
  → Rayyan · Covidence · ASReview · your pipeline
```

## Packages

| Package | PyPI | Description |
|---------|------|-------------|
| `litprism-pubmed` | — | PubMed / MEDLINE via NCBI E-utilities |
| `litprism-europepmc` | — | Europe PMC (preprints, patents, MEDLINE supplement) |
| `litprism-semanticscholar` | — | Semantic Scholar (cross-disciplinary, 200M+ papers) |
| `litprism-crossref` | — | Crossref metadata enrichment |
| `litprism-screen` | — | LLM screening with grounded per-criterion decisions |

## Status

Pre-release. See [litprism-spec-v6.md](litprism-spec-v6.md) for the full specification.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
