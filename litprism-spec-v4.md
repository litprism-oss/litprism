# LitPrism — Project Specification v4
> Open-source search, screening, and audit layer for evidence synthesis
> Version: 0.4-draft | Status: Pre-implementation

---

## 0. Name & Domain Notes

**Working name: LitPrism**
- Meaning: a prism refracts and filters — exactly what the tool does to literature
- Easter egg: nod to PRISMA reporting standard used in systematic reviews
- Check before committing: `litprism.io`, `litprism.org` on Cloudflare/Namecheap
- PyPI namespace: `litprism-pubmed`, `litprism-europepmc`, `litprism-screen`, etc.
- GitHub: `github.com/yourname/litprism` or org `github.com/litprism`

If `litprism` is taken on PyPI or domain, top alternatives in order:
`litscout`, `sciprism`, `paperprism`, `evidflow`

---

## 1. Vision

**LitPrism** fills the gap every existing systematic review tool skips:
**integrated multi-source search with reproducible, publication-ready audit trails.**

Every existing tool — Rayyan, Covidence, ASReview, DistillerSR — requires
researchers to manually search each database, export files, and import them.
LitPrism automates that entire layer, then optionally screens with an LLM,
and exports a clean auditable set ready for any downstream tool or journal submission.

```
Natural language / PICO / direct query
              ↓
   LitPrism: Search → Dedup → Screen
   + PRISMA-S compliant search record
              ↓
  .nbib / .ris / .csv / ASReview format
  → Rayyan · Covidence · ASReview · your pipeline
```

### What LitPrism is
- The **search + ingest + screening layer** that feeds any downstream SR tool
- Standalone **Python packages** independently installable from PyPI
- A **self-hostable web app** with simple and advanced modes
- **BYOLLM**: OpenAI, Azure OpenAI, or local Ollama — user brings their own key
- **Publication-ready**: auto-generates PRISMA-S supplementary tables for systematic
  and scoping reviews

### What LitPrism is not
- A replacement for ASReview, Covidence, or Rayyan
- A meta-analysis or statistical synthesis tool
- A report/manuscript writing tool (deferred to v2)

### Landscape gap confirmed
No existing open-source or commercial tool has:
- Built-in multi-source search with per-source query translation
- Automatic PRISMA-S compliant search record generation
- LLM screening with source-grounded per-criterion decisions
- BYOLLM including local Ollama
- Export that feeds directly into ASReview with labels

---

## 2. Review Types Supported

LitPrism supports five review types. The review type selected at project creation
controls how strictly the tool enforces reproducibility requirements.

```python
class ReviewType(str, Enum):
    SYSTEMATIC   = "systematic"     # PRISMA 2020 + PRISMA-S, full rigour
    SCOPING      = "scoping"        # PRISMA-ScR, broad mapping
    RAPID        = "rapid"          # Cochrane rapid review, simplified rigour
    LITERATURE   = "literature"     # No formal standard, flexible
    STATE_OF_ART = "state_of_art"   # CS/engineering, no standard
```

### How review type affects the tool

| Feature | Systematic | Scoping | Rapid | Literature | State-of-Art |
|---------|-----------|---------|-------|------------|-------------|
| PICO input form | ✅ | Optional | ✅ | ❌ | ❌ |
| Query locked after execution | ✅ Required | ✅ Required | ✅ Required | ❌ Flexible | ❌ Flexible |
| Search date recorded per source | ✅ | ✅ | ✅ | Optional | Optional |
| Per-source query stored verbatim | ✅ | ✅ | ✅ | Optional | Optional |
| PRISMA-S export | ✅ PRISMA 2020 | ✅ PRISMA-ScR | ✅ Simplified | ❌ | ❌ |
| Dual screening mode available | ✅ | ✅ | Optional | ❌ | ❌ |
| Inclusion/exclusion criteria | Strict, predefined | Moderate | Strict | Informal | Informal |
| UI label for criteria | "Eligibility criteria" | "Eligibility criteria" | "Eligibility criteria" | "Relevance filters" | "Relevance filters" |
| LLM screening conservatism | High | Medium | High | Low | Low |

### Reproducibility — the key architectural implication

For systematic, scoping, and rapid reviews, search strings are **publishable
research output**, not internal implementation details. Journals require:

- Exact search string per database as actually executed
- Database name and interface/platform
- Date each database was last searched (timezone-aware)
- Filters applied (date range, language, article type)
- Result count per database before deduplication

**LitPrism auto-generates this as a PRISMA-S supplementary table** — the table
researchers currently build by hand. This is a genuine differentiator.

For literature and state-of-the-art reviews, none of this is required — queries
stay editable, no locking, simpler experience.

---

## 3. Monorepo Structure

```
litprism/
├── pyproject.toml                        # uv workspace root
├── uv.lock
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                        # lint + test per package on PR
│   │   └── publish.yml                   # per-package PyPI publish on tag
│   └── CONTRIBUTING.md
├── packages/
│   ├── litprism-pubmed/
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── CHANGELOG.md
│   │   └── src/litprism/pubmed/
│   │       ├── __init__.py
│   │       ├── client.py                 # PubMedClient, AsyncPubMedClient
│   │       ├── models.py
│   │       ├── entrez.py                 # raw E-utilities wrapper
│   │       ├── parser.py                 # XML → Pydantic
│   │       ├── cache.py                  # optional SQLite cache
│   │       └── exceptions.py
│   │
│   ├── litprism-europepmc/
│   │   ├── pyproject.toml
│   │   └── src/litprism/europepmc/
│   │       ├── __init__.py
│   │       ├── client.py
│   │       ├── models.py
│   │       └── exceptions.py
│   │
│   ├── litprism-semanticscholar/
│   │   ├── pyproject.toml
│   │   └── src/litprism/semanticscholar/
│   │       ├── __init__.py
│   │       ├── client.py
│   │       ├── models.py
│   │       └── exceptions.py
│   │
│   ├── litprism-crossref/
│   │   ├── pyproject.toml
│   │   └── src/litprism/crossref/
│   │       ├── __init__.py
│   │       ├── client.py                 # enrichment only, not primary search
│   │       └── models.py
│   │
│   └── litprism-screen/
│       ├── pyproject.toml
│       └── src/litprism/screen/
│           ├── __init__.py
│           ├── screener.py
│           ├── criteria.py
│           ├── models.py
│           ├── prompts.py
│           ├── grounding.py
│           └── llm.py
│
└── apps/
    └── litprism-app/
        ├── backend/
        │   ├── api/
        │   │   ├── projects.py
        │   │   ├── search.py
        │   │   ├── screening.py
        │   │   ├── upload.py
        │   │   ├── export.py
        │   │   └── chat.py
        │   ├── db/
        │   │   ├── models.py
        │   │   └── migrations/           # Alembic
        │   ├── services/
        │   │   ├── pipeline.py           # simple mode orchestration
        │   │   ├── query_builder.py      # LLM query generation
        │   │   ├── query_translator.py   # per-source syntax adaptation
        │   │   ├── dedup.py
        │   │   ├── upload.py
        │   │   └── export.py
        │   └── main.py
        └── frontend/                     # React + TypeScript + Vite
```

---

## 4. Tooling Standards

| Tool | Purpose |
|------|---------|
| `uv` | Package manager + workspace |
| `ruff` | Lint + format (line-length=100, select E/F/I/UP/B/SIM) |
| `pytest` + `pytest-asyncio` | Testing (asyncio_mode=auto) |
| `pydantic v2` | All data models |
| `litellm` | LLM provider abstraction |
| `httpx` | Async HTTP client |
| Python | `>=3.11` |

**Tag format:** `litprism-pubmed/v0.1.0`, `litprism-screen/v0.2.1`

---

## 5. Search Sources

### Source tiers

**Free tier — default, no keys needed:**

| Package | Source | Coverage | API | Rate limit |
|---------|--------|----------|-----|-----------|
| `litprism-pubmed` | PubMed / MEDLINE | 36M+ biomedical | NCBI E-utilities | 10/s with key, 3/s without |
| `litprism-europepmc` | Europe PMC | 40M+ life science + preprints + patents | EBI REST, no auth | 10/s |
| `litprism-semanticscholar` | Semantic Scholar | 200M+ all disciplines | Official REST | 100/10s, key optional |
| `litprism-crossref` | Crossref | 165M+ DOIs | REST, polite pool | Generous with email |

**Institutional tier — user brings key (v2):**
Scopus (Elsevier), Web of Science (Clarivate), Embase (Elsevier)

**Paid tier — user brings key (v2):**
Google Scholar via SerpAPI

**Dropped:** OpenAlex — unreliable abstracts and metadata confirmed in production use.

### Source roles

- **PubMed**: biomedical gold standard, MeSH-indexed, fully reproducible
- **Europe PMC**: ingests all PubMed + adds preprints (34 servers incl. bioRxiv),
  patents, Agricola, full-text search — best free PubMed supplement
- **Semantic Scholar**: strongest free option for CS, AI, engineering,
  cross-disciplinary; weak on older biomedical literature
- **Crossref**: passive enrichment layer only — fills missing metadata (publisher,
  funder, license, open-access) for articles found via other sources. Not searched
  directly.

### Why not OpenAlex

OpenAlex is an aggregator. Aggregators have inconsistent abstracts, metadata gaps,
and API instability — confirmed through production use. Primary databases (PubMed,
Europe PMC, Semantic Scholar) that index their own curated content are more reliable.

---

## 6. Shared Article Model

All source clients normalise output to a common `Article` model.
This is the contract between search packages and the screening package.
Each package defines its own copy — no cross-imports between packages.

```python
from pydantic import BaseModel
from datetime import date, datetime
from typing import Protocol, Literal

class Author(BaseModel):
    last_name: str
    fore_name: str | None = None
    affiliation: str | None = None
    orcid: str | None = None

class Article(BaseModel):
    # Identity — at least one of these must be present
    id: str                            # source-specific internal id
    pmid: str | None = None
    doi: str | None = None
    source: str                        # "pubmed"|"europepmc"|"semanticscholar"|"upload"

    # Content
    title: str
    abstract: str | None = None
    authors: list[Author] = []
    journal: str | None = None
    publication_date: date | None = None
    publication_year: int | None = None

    # Access
    open_access: bool = False
    pdf_url: str | None = None
    full_text_url: str | None = None

    # Source extras
    mesh_terms: list[str] = []         # PubMed, Europe PMC
    keywords: list[str] = []
    article_types: list[str] = []
    citation_count: int | None = None  # Semantic Scholar

# Protocol — satisfied by Article without importing litprism-screen
class ScreenableArticle(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def title(self) -> str: ...
    @property
    def abstract(self) -> str | None: ...
```

---

## 7. Package Specifications

### 7.1 litprism-pubmed

Refactor of existing code. Key public API:

```python
from litprism.pubmed import PubMedClient, AsyncPubMedClient

client = PubMedClient(api_key="...")   # optional

result = client.search(
    query='("Crohn disease"[MeSH]) AND probiotic*[tiab]',
    max_results=500,
    date_range=("2015-01-01", "2024-12-31"),
    filters=ArticleFilters(
        article_types=["Clinical Trial", "Review"],
        languages=["eng"],
        has_abstract=True,
    )
)
articles: list[Article] = client.fetch(result.pmids)
```

Internals: token-bucket rate limiting, auto-chunk PMIDs into batches of 200,
optional SQLite cache keyed on PMID+fetch_date.

### 7.2 litprism-europepmc

```python
from litprism.europepmc import EuropePMCClient

client = EuropePMCClient()   # no auth required

articles = client.search(
    query='(MESH:"Crohn Disease") AND probiotic*',
    max_results=500,
    date_range=("2015", "2024"),
    source_filter=["MED", "PMC", "PPR"],  # MED=MEDLINE, PPR=preprints
    has_abstract=True,
)
```

Notes: auto MeSH synonym expansion (can disable), cursor-based pagination via
`cursorMark` for >10,000 results, returns PMID where available for cross-source dedup.

### 7.3 litprism-semanticscholar

```python
from litprism.semanticscholar import SemanticScholarClient

client = SemanticScholarClient(api_key="...")  # optional

articles = client.search(
    query="Crohn disease probiotic gut microbiome",  # keyword only
    max_results=500,
    year_range=("2015", "2024"),
    fields_of_study=["Medicine", "Biology"],
)
```

Notes: no boolean/field syntax, keyword relevance only.
`externalIds.PubMed` and `externalIds.DOI` used for dedup cross-linking.

### 7.4 litprism-crossref (enrichment only)

```python
from litprism.crossref import CrossrefClient

client = CrossrefClient(mailto="you@example.com")  # polite pool

# Not searched directly — called after dedup to fill metadata gaps
meta = client.enrich_by_doi("10.1016/j.crohns.2021.01.001")
meta.publisher, meta.license, meta.funder, meta.open_access_status
```

### 7.5 litprism-screen

See Sections 10–11 for full detail.

---

## 8. Search Input: Three Modes

```
Mode A — Natural language (both simple + advanced)
  "What is the effect of probiotics on gut microbiome in Crohn's disease?"

Mode B — PICO form (advanced, clinical/health research)
  Population:    Adults with Crohn's disease
  Intervention:  Probiotic supplementation
  Comparison:    Placebo or no treatment
  Outcome:       Gut microbiome composition, disease activity score

Mode C — Direct PubMed query entry (advanced, power users)
  ("Crohn disease"[MeSH] OR "Crohn's disease"[tiab]) AND probiotic*[tiab]
```

Modes A and B feed the LLM query builder which generates a canonical PubMed
syntax query. Mode C bypasses the LLM entirely. The user always reviews and
can edit the canonical query before execution.

### LLM query builder prompt

```
You are a biomedical literature search specialist.
Generate a PubMed-compatible boolean search query.

Rules:
- MeSH terms: "term"[MeSH]
- Title+abstract: term[tiab], title only: term[ti]
- Truncation: probiotic* for variants
- Boolean: AND, OR, NOT (uppercase)
- Date range if specified: "YYYY/MM/DD"[Date - Publication] : "YYYY/MM/DD"[Date - Publication]
- Group with parentheses

Input: {user_input}

Return ONLY the query string. No explanation.
```

---

## 9. Query Translation

One canonical PubMed-syntax query is generated and approved by the user.
`QueryTranslator` adapts it per source before execution. Per-source strings
are stored verbatim as the executed query — this is what gets published.

```python
import re

class QueryTranslator:

    @staticmethod
    def to_pubmed(query: str) -> str:
        return query

    @staticmethod
    def to_europepmc(query: str) -> str:
        q = query
        q = re.sub(r'"([^"]+)"\[MeSH(?:[^\]]*)\]', r'MESH:"\1"', q)
        q = re.sub(r'(\S+)\[tiab\]', r'\1', q)        # tiab = default in EPMC
        q = re.sub(r'(\S+)\[ti\]',   r'TITLE:\1', q)
        q = re.sub(r'(\S+)\[ab\]',   r'ABSTRACT:\1', q)
        q = re.sub(r'(\S+)\[au\]',   r'AUTH:"\1"', q)
        q = re.sub(
            r'"(\d{4}/\d{2}/\d{2})"\[Date - Publication\] : '
            r'"(\d{4}/\d{2}/\d{2})"\[Date - Publication\]',
            r'FIRST_PDATE:[\1 TO \2]', q
        )
        q = re.sub(r'([\w\s]+)\[pt\]', r'PUB_TYPE:\1', q)
        return q.strip()

    @staticmethod
    def to_semantic_scholar(query: str) -> str:
        q = re.sub(r'"([^"]+)"\[MeSH(?:[^\]]*)\]', r'"\1"', query)
        q = re.sub(r'\[\w+\]', '', q)
        q = re.sub(r'\s+', ' ', q).strip()
        return q

    @staticmethod
    def to_scopus(query: str) -> str:
        # Institutional tier v2
        q = re.sub(r'"([^"]+)"\[MeSH(?:[^\]]*)\]', r'"\1"', query)
        q = re.sub(r'(\S+)\[tiab\]', r'TITLE-ABS-KEY(\1)', q)
        q = re.sub(r'(\S+)\[ti\]',   r'TITLE(\1)', q)
        q = re.sub(r'(\S+)\[ab\]',   r'ABS(\1)', q)
        return q.strip()
```

### What the user sees

After approving the canonical query, a collapsible panel shows per-source
adaptations — read-only by default, editable on demand (advanced mode only):

```
Canonical (PubMed):
  ("Crohn disease"[MeSH] OR "Crohn's disease"[tiab]) AND probiotic*[tiab]

Europe PMC:      MESH:"Crohn disease" OR "Crohn's disease" AND probiotic*
Semantic Scholar: "Crohn disease" OR "Crohn's disease" probiotic
                  [Edit ▾]
```

In simple mode this is hidden entirely.

---

## 10. Search Record & Reproducibility

This is LitPrism's core differentiator for rigorous reviews.

### SearchRun model

```python
from datetime import datetime, timezone

class SourceQuery(BaseModel):
    source: str                   # "pubmed" | "europepmc" | "semanticscholar"
    interface: str                # "NCBI E-utilities v2" | "EBI REST API v6" etc.
    query_string: str             # exact string sent to the API — immutable after lock
    filters_applied: dict         # date_range, article_types, language, etc.
    searched_at: datetime         # timezone-aware UTC timestamp
    result_count: int             # raw hits before dedup

class SearchRun(BaseModel):
    id: str
    project_id: str
    review_type: ReviewType

    # Input chain — preserved for audit
    query_natural: str            # what user typed in natural language
    query_generated: str          # LLM output
    query_final: str              # what user approved (may differ)

    # Per-source — populated at execution, then locked
    source_queries: list[SourceQuery]

    # Lifecycle
    status: Literal["draft", "locked", "completed", "failed"]
    locked_at: datetime | None    # set the moment search fires, never changes
    completed_at: datetime | None
```

### Locking behaviour by review type

```python
def should_lock(review_type: ReviewType) -> bool:
    return review_type in (
        ReviewType.SYSTEMATIC,
        ReviewType.SCOPING,
        ReviewType.RAPID,
    )
```

When a search is locked:
- The canonical query and all per-source queries are frozen
- Editing is blocked — user must start a new search run
- A "Search record locked" badge is displayed with the date
- The PRISMA-S export becomes available

For literature and state-of-the-art, no locking — queries remain editable.

### PRISMA-S export

Auto-generated supplementary table, ready to paste into a journal submission:

```
Database      Interface              Date searched    Results
─────────────────────────────────────────────────────────────
MEDLINE       NCBI E-utilities       14 March 2024    847

Search string:
  ("Crohn disease"[MeSH Terms] OR "Crohn's disease"[Title/Abstract])
  AND (probiotic*[Title/Abstract] OR "Lactobacillus"[MeSH Terms])
  AND ("2015/01/01"[Date - Publication] : "2024/12/31"[Date - Publication])

Filters: English language, has abstract

─────────────────────────────────────────────────────────────
Europe PMC    EBI REST API           14 March 2024    612

Search string:
  MESH:"Crohn Disease" OR "Crohn's disease" AND probiotic*
  AND FIRST_PDATE:[2015 TO 2024]

─────────────────────────────────────────────────────────────
Semantic      S2 Academic Graph API  14 March 2024    234
Scholar

Search string:
  "Crohn disease" OR "Crohn's disease" probiotic

─────────────────────────────────────────────────────────────
Total before deduplication:                          1,693
After deduplication:                                 1,241
```

---

## 11. LLM Provider Configuration

```python
from pydantic import BaseModel
from typing import Literal

class OpenAIConfig(BaseModel):
    provider: Literal["openai"] = "openai"
    api_key: str
    model: str = "gpt-4o-mini"

class AzureOpenAIConfig(BaseModel):
    provider: Literal["azure"] = "azure"
    api_key: str
    azure_endpoint: str           # https://myresource.openai.azure.com
    azure_deployment: str         # e.g. "gpt-4o"
    api_version: str = "2024-02-01"
    model: str = "azure/gpt-4o"   # LiteLLM requires azure/ prefix

class OllamaConfig(BaseModel):
    provider: Literal["ollama"] = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "llama3.1"

LLMConfig = OpenAIConfig | AzureOpenAIConfig | OllamaConfig
```

```python
import litellm

async def call_llm(config: LLMConfig, prompt: str, system: str | None = None) -> str:
    kwargs = dict(
        model=config.model,
        messages=[
            *([ {"role": "system", "content": system} ] if system else []),
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    if isinstance(config, AzureOpenAIConfig):
        kwargs.update(
            api_key=config.api_key,
            api_base=config.azure_endpoint,
            api_version=config.api_version,
        )
    elif isinstance(config, OllamaConfig):
        kwargs["api_base"] = config.base_url

    response = await litellm.acompletion(**kwargs)
    return response.choices[0].message.content
```

**Environment variable fallback:**
```bash
# OpenAI
LLM_PROVIDER=openai   OPENAI_API_KEY=sk-...   LLM_MODEL=gpt-4o-mini

# Azure OpenAI
LLM_PROVIDER=azure    AZURE_API_KEY=...        AZURE_API_BASE=https://...
                      AZURE_API_VERSION=2024-02-01
                      AZURE_DEPLOYMENT_NAME=gpt-4o

# Ollama (no key)
LLM_PROVIDER=ollama   OLLAMA_BASE_URL=http://localhost:11434
                      LLM_MODEL=llama3.1
```

---

## 12. LLM Screening with Grounding

### Two stages, same Screener interface

```
Stage 1: Abstract screening   → fast, cheap, 100–2000 articles
Stage 2: Full-text screening  → slower, 20–200 articles, PDF-based
```

Screening conservatism is tuned per review type:
- Systematic / Rapid: high conservatism — prefer "uncertain" over "exclude"
- Scoping: medium — broader inclusion acceptable
- Literature / State-of-art: low — flexible filtering

### Models

```python
class Criteria(BaseModel):
    inclusion: list[str]
    exclusion: list[str]
    uncertain_threshold: float = 0.75   # confidence below this → uncertain

class CriteriaHit(BaseModel):
    criterion: str
    criterion_type: Literal["inclusion", "exclusion"]
    triggered: bool
    supporting_quote: str | None = None   # verbatim from title/abstract
    quote_location: Literal["title", "abstract", "section"] | None = None

class ScreeningDecision(str, Enum):
    INCLUDE   = "include"
    EXCLUDE   = "exclude"
    UNCERTAIN = "uncertain"

class ScreeningResult(BaseModel):
    article_id: str
    decision: ScreeningDecision
    confidence: float                    # 0.0–1.0
    reasoning: str                       # 2–3 sentences
    criteria_hits: list[CriteriaHit]    # one per criterion, grounded
    stage: Literal["abstract", "fulltext"]
    model_used: str
    llm_provider: str
    screened_at: datetime
    human_override: bool = False
    human_decision: ScreeningDecision | None = None
    human_note: str | None = None
```

### Abstract screening prompt

```
You are screening research articles for a {review_type} review.
Your decisions must be grounded in exact text from the article.

INCLUSION CRITERIA:
{inclusion_criteria}

EXCLUSION CRITERIA:
{exclusion_criteria}

ARTICLE:
Title: {title}
Abstract: {abstract}

Instructions:
- For each criterion, decide if it is triggered (true/false)
- If triggered, copy the exact phrase from the title or abstract
- If a criterion cannot be assessed from abstract alone, mark
  triggered=false, supporting_quote="insufficient information in abstract"
- Decision logic:
    include   → ALL inclusion criteria met AND NO exclusion criteria triggered
    exclude   → ANY exclusion criterion triggered
    uncertain → key criteria cannot be assessed from abstract alone
- Conservatism level: {conservatism_instruction}

Respond ONLY in JSON:
{{
  "decision": "include"|"exclude"|"uncertain",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence explanation referencing specific criteria",
  "criteria_hits": [
    {{
      "criterion": "<exact criterion text>",
      "criterion_type": "inclusion"|"exclusion",
      "triggered": true|false,
      "supporting_quote": "<verbatim phrase or null>",
      "quote_location": "title"|"abstract"|null
    }}
  ]
}}
```

Where `{conservatism_instruction}` resolves to:
- Systematic/Rapid: `"When in doubt, prefer 'uncertain' over 'exclude'. Err on the side of inclusion."`
- Scoping: `"Use moderate conservatism. Uncertain is acceptable for genuinely ambiguous cases."`
- Literature/State-of-Art: `"Use flexible judgment. Exclude clearly irrelevant articles."`

### Full-text screening

- PDF extracted via `pdfplumber`
- Section detection: `/^(Abstract|Introduction|Methods?|Results?|Discussion|Conclusion)/im`
- Each section screened independently → `SectionScreeningResult`
- Final decision: synthesis call with all section results
- Supporting quote from most diagnostic section

### Human review UI (what grounding enables)

```
[EXCLUDED — 91% confidence]

✗ Animal studies (exclusion):  TRIGGERED
  → "Wistar rats were randomly assigned to..." [abstract]

✓ Human subjects (inclusion): not met
✓ Clinical outcomes (inclusion): cannot assess from abstract

[Override → Include]  [Override → Uncertain]  [Add note]
```

---

## 13. Document Upload

Supported: `.pdf`, `.nbib`, `.ris`, `.bib`, `.csv`

All parsed into the shared `Article` model.
Uploaded PDFs stored at `~/.litprism/uploads/<project_id>/`
(configurable via `UPLOAD_DIR`; optional S3-compatible via `STORAGE_BACKEND=s3`).

**Deduplication on upload:**
- Exact match: DOI or PMID → auto-merge
- Fuzzy: title similarity ≥ 0.92 (rapidfuzz) + same first author → flag for review

---

## 14. Deduplication

Run after all sources fetched and uploads ingested.

**Canonical record priority:** PubMed > Europe PMC > Semantic Scholar > upload

```python
class DeduplicationResult(BaseModel):
    kept: Article
    duplicates: list[Article]
    match_type: Literal["exact_pmid", "exact_doi", "fuzzy_title"]
    similarity_score: float | None = None
```

All decisions logged to `deduplication_log` — contributes to PRISMA flow counts.

---

## 15. Export Integrations

```python
exporter = ExportService(project_id=project.id)

exporter.to_nbib("screened.nbib")         # Rayyan, Covidence, Zotero, EndNote
exporter.to_ris("screened.ris")           # most SR tools
exporter.to_csv("screened.csv")           # ASReview, Excel, R
exporter.to_json("screened.json")         # custom pipelines
exporter.to_asreview("screened.asreview") # ASReview native with labels
exporter.to_prisma_s("search_record.docx|csv")  # PRISMA-S supplementary table
```

**ASReview export** includes `label_included=1/0` so users can continue
active learning in ASReview from where LitPrism left off.

**PRISMA-S export** generates the supplementary table (Section 10) in both
CSV and Word document formats, ready for journal submission.

---

## 16. Data Storage

SQLite default (zero config), PostgreSQL via `DATABASE_URL`. Same models.

### Schema (v1)

```sql
-- Projects
projects (id, name, description, research_question, review_type, created_at)

-- Search
search_runs (
  id, project_id,
  query_natural, query_generated, query_final,
  status,           -- draft | locked | completed | failed
  locked_at,        -- set when search fires, never changes (rigorous reviews)
  completed_at
)

source_queries (
  id, search_run_id,
  source, interface, query_string,
  filters_applied,  -- JSON
  searched_at,      -- UTC timestamp
  result_count
)

-- Articles
articles (
  id, project_id, search_run_id,
  pmid, doi, europepmc_id, semantic_scholar_id,
  title, abstract, authors,   -- JSON
  journal, pub_date, source, file_path, created_at
)

deduplication_log (
  id, project_id, kept_article_id, duplicate_article_id,
  match_type, similarity_score
)

-- Screening
criteria (
  id, project_id,
  inclusion,              -- JSON array
  exclusion,              -- JSON array
  uncertain_threshold,
  created_at
)

screening_results (
  id, article_id, project_id,
  stage,                  -- abstract | fulltext
  decision, confidence, reasoning,
  criteria_hits,          -- JSON with supporting_quote per hit
  model_used, llm_provider,
  human_override, human_decision, human_note,
  screened_at, overridden_at
)

-- Chat
chat_messages (
  id, project_id, role, content,
  context_snapshot,       -- JSON snapshot of project state at message time
  created_at
)
```

### PRISMA flow (derived at query time, never stored separately)

```python
class PRISMAFlow(BaseModel):
    # Search
    identified_pubmed: int
    identified_europepmc: int
    identified_semanticscholar: int
    identified_uploads: int
    identified_total: int

    # Dedup
    duplicates_removed: int
    after_deduplication: int

    # Screening
    screened_abstract: int
    excluded_abstract: int
    uncertain_abstract: int
    human_overrides_abstract: int

    sought_fulltext: int
    excluded_fulltext: int
    human_overrides_fulltext: int

    included_final: int

    # Top exclusion reasons (derived from criteria_hits)
    top_exclusion_reasons: list[tuple[str, int]]
```

---

## 17. Research Assistant Chat

Scoped to current project. Advises — never acts unilaterally.

### Context injected per message

```python
system = f"""
You are a research assistant for a {review_type} project.

PROJECT: {project.name}
RESEARCH QUESTION: {project.research_question}
REVIEW TYPE: {review_type}

SEARCH:
  Query: {latest_search.query_final}
  Sources: {[sq.source for sq in latest_search.source_queries]}
  Date: {latest_search.locked_at}

ELIGIBILITY CRITERIA:
  Inclusion: {criteria.inclusion}
  Exclusion: {criteria.exclusion}

SCREENING PROGRESS:
  Total articles: {flow.after_deduplication}
  Abstract screened: {flow.screened_abstract}
    Included: {flow.included_abstract}
    Excluded: {flow.excluded_abstract}
    Uncertain: {flow.uncertain_abstract}
  Full-text screened: {flow.screened_fulltext}
  Final included: {flow.included_final}

TOP EXCLUSION REASONS:
  {flow.top_exclusion_reasons}

You may reference specific articles by title.
You do not modify data — the user acts, you advise.
"""
```

### Capabilities in v1

- Explain any screening decision (*"why was Smith 2021 excluded?"*)
- Summarise by exclusion reason (*"how many excluded for being animal studies?"*)
- Suggest criteria refinements (*"our exclusion rate is 94% — is that normal?"*)
- Suggest additional MeSH terms or search terms
- Guide next step (*"should I proceed to full-text screening?"*)
- Help interpret PRISMA flow numbers

---

## 18. Simple vs Advanced Mode

Same backend, same packages, different orchestration.

### Simple mode (researchers — non-developer)

```
① Enter research question (free text) or PICO form
② Review LLM-generated PubMed query → [Confirm]
③ Sources auto-selected (PubMed + Europe PMC + Semantic Scholar)
④ Review dedup summary → [Proceed]
⑤ Review LLM-suggested criteria → edit → [Confirm]
⑥ Run abstract screening → stats summary → [Proceed]
⑦ Upload PDFs for uncertain + included → run full-text → [Proceed]
⑧ Export (choose format)
```

Assistant is proactive at each step. User clicks Confirm/Proceed.
Per-source query translations are invisible.
For rigorous review types, search locks silently before execution.

### Advanced mode (developers, librarians, power users)

Separate page per step with full control:
- Write/edit canonical query
- View and individually edit per-source translations
- Choose sources manually, set per-source filters
- Browse raw results before dedup, override merge decisions
- Define criteria with rich editor, test against sample articles
- Article-by-article review with grounded criteria hits
- Batch operations, bulk override
- Full PRISMA flow dashboard with drill-down

---

## 19. Phase Build Plan (v1)

| Phase | Deliverable | Notes |
|-------|------------|-------|
| 1 | Monorepo scaffold + CI/CD | uv workspace, ruff, pytest, GitHub Actions |
| 2 | `litprism-pubmed` | Refactor existing code to spec |
| 3 | `litprism-europepmc` | New |
| 4 | `litprism-semanticscholar` | New |
| 5 | `litprism-crossref` | Enrichment only |
| 6 | `litprism-screen` abstract stage | LLM + grounding + review-type conservatism |
| 7 | `litprism-screen` full-text stage | PDF chunking + section grounding |
| 8 | App backend | DB, upload, search pipeline, dedup, PRISMA-S export, chat |
| 9 | App frontend | React wizard (simple) + step UI (advanced) |

**v2 (future):**
- `litprism-extract` — structured data extraction
- `litprism-report` — report generation
- Institutional sources: Scopus, Web of Science, Embase
- Dual screening / reviewer collaboration

---

## 20. Claude Code Instructions

Hand this document to Claude Code with this prompt:

```
Read litprism-spec-v4.md in full before writing any code.
Use the name "LitPrism" and package namespace "litprism" throughout.
Build phases strictly in order — do not jump ahead.

PHASE 1 — Monorepo
- uv init litprism
- Root pyproject.toml:
    [tool.uv.workspace] members = ["packages/*", "apps/*"]
    [tool.ruff] line-length=100, target-version="py311"
    [tool.ruff.lint] select=["E","F","I","UP","B","SIM"]
    [tool.pytest.ini_options] asyncio_mode="auto"
- Python: >=3.11
- .github/workflows/ci.yml:
    matrix over packages, run: ruff check + pytest per package
- .github/workflows/publish.yml:
    trigger on tag: litprism-{package}/v*, publish to PyPI

PHASE 2 — litprism-pubmed
- Scaffold packages/litprism-pubmed/src/litprism/pubmed/
- Implement in order:
    exceptions.py → models.py → entrez.py → parser.py → cache.py → client.py
- PubMedClient (sync) wraps AsyncPubMedClient
- Rate limiting: token bucket, 3/s without key, 10/s with key
- Batch fetch: auto-chunk PMIDs into batches of 200
- Tests: test_parser.py with fixture XML, test_client.py with httpx mock
- I will provide existing pubmed-py code to align against spec after scaffold

PHASE 3 — litprism-europepmc
- Scaffold packages/litprism-europepmc/src/litprism/europepmc/
- REST: https://www.ebi.ac.uk/europepmc/webservices/rest/search
- Cursor pagination via cursorMark for >10,000 results
- Normalise to shared Article model (copy don't import from pubmed)
- source_filter param: accept list of MED|PMC|PPR
- Tests with httpx mock + fixture JSON

PHASE 4 — litprism-semanticscholar
- Scaffold packages/litprism-semanticscholar/src/litprism/semanticscholar/
- Wrap https://api.semanticscholar.org/graph/v1/paper/search
- Optional api_key for higher rate limits
- Normalise: map externalIds.PubMed → pmid, externalIds.DOI → doi
- Tests with httpx mock

PHASE 5 — litprism-crossref
- Scaffold packages/litprism-crossref/src/litprism/crossref/
- Wrap https://api.crossref.org/works/{doi}
- Enrichment only: enrich_by_doi() → CrossrefMetadata
- Always send mailto= in User-Agent (polite pool)

PHASE 6 — litprism-screen (abstract)
- Scaffold packages/litprism-screen/src/litprism/screen/
- LLMConfig union per spec §11 with call_llm() implementation
- ReviewType enum per spec §2
- Criteria, CriteriaHit, ScreeningResult models per spec §12
- prompts.py: abstract_screening_prompt(review_type) — conservatism varies by type
- grounding.py: parse LLM JSON response, validate supporting_quote present
- screener.py: Screener.ascreen_batch() with asyncio.gather, batch_size=10
- Tests: mock LLM response, verify CriteriaHit parsing, quote extraction,
  and that conservatism instruction changes per review type

PHASE 7 — litprism-screen (full-text)
- pdfplumber for PDF text extraction
- Section detection: /^(Abstract|Introduction|Methods?|Results?|Discussion|Conclusion)/im
- SectionScreeningResult model
- Synthesise section results → FullTextScreeningResult
- supporting_quote from most diagnostic section

PHASE 8 — litprism-app backend
- FastAPI + SQLAlchemy (async) + Alembic migrations
- DB schema per spec §16 exactly
- Services:
    query_builder.py  — LLM canonical query generation
    query_translator.py — QueryTranslator per spec §9
    dedup.py          — rapidfuzz title matching + DOI/PMID exact match
    export.py         — nbib, ris, csv, json, asreview, prisma_s
- SearchRun locking logic per spec §10
  (lock_search_run() sets locked_at, freezes source_queries)
- PRISMAFlow computed at query time from DB per spec §16
- Endpoints:
    POST   /api/projects
    GET    /api/projects/{id}
    GET    /api/projects/{id}/prisma
    POST   /api/projects/{id}/search/generate-query
    POST   /api/projects/{id}/search/run
    GET    /api/projects/{id}/search/{run_id}
    POST   /api/projects/{id}/upload
    POST   /api/projects/{id}/deduplicate
    POST   /api/projects/{id}/screen/abstract
    POST   /api/projects/{id}/screen/fulltext
    PATCH  /api/projects/{id}/articles/{aid}/override
    GET    /api/projects/{id}/export?format=nbib|ris|csv|json|asreview|prisma_s
    POST   /api/projects/{id}/chat
    POST   /api/projects/{id}/run          (simple mode full pipeline)
- Celery + Redis for long-running tasks
- WebSocket /ws/projects/{id}/progress

PHASE 9 — litprism-app frontend
- React + TypeScript + Vite
- Project creation: review type selector (systematic|scoping|rapid|literature|state_of_art)
- Simple mode: step wizard with progress indicator + assistant panel
- Advanced mode: per-step pages with full query editing
- Per-source query preview panel (collapsible, editable in advanced mode)
- Search record badge: "Search locked — 14 March 2024" for rigorous types
- Screening review: article card showing criteria hits with supporting quotes
- Human override UI per spec §12
- PRISMA flow dashboard with drill-down
- Export page: format picker, PRISMA-S download for rigorous types
- Chat sidebar: context auto-injected, visible at all steps
```
