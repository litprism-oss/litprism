# litprism-screen

LLM-powered abstract and full-text screening for systematic reviews,
with source grounding and per-criterion audit trails.

Part of the [LitPrism](https://litprism.org) open-source evidence synthesis platform.

```bash
pip install litprism-screen
```

---

## Overview

`litprism-screen` automates the most labour-intensive step in a systematic
review — screening hundreds or thousands of titles and abstracts against
eligibility criteria — while producing a fully auditable, per-criterion
decision trail that satisfies publication standards.

The package implements the two-stage screening workflow standard in
systematic review methodology:

```
Stage 1 — Abstract screening   (fast, cheap: 100–2000 articles)
         ↓ uncertain → Stage 2
Stage 2 — Full-text screening  (thorough: 20–200 articles, text-based)
```

**Scope of this package:** `litprism-screen` handles screening logic only.
It accepts text as input (title + abstract for Stage 1; extracted full text
for Stage 2). PDF parsing and full-text retrieval are handled upstream by
the `litprism-app` pipeline — see [Full-text screening](#full-text-screening-stage-2)
for details.

---

## Quick start

```python
from litprism.screen import Screener
from litprism.screen.criteria import Criteria
from litprism.screen.models import ReviewType

# Configure your LLM provider (reads LLM_PROVIDER + keys from environment)
screener = Screener.from_env()

# Define your eligibility criteria
criteria = Criteria(
    review_type=ReviewType.SYSTEMATIC,
    inclusion=[
        "Randomised controlled trial or quasi-randomised trial",
        "Adult participants (≥18 years)",
        "Probiotic intervention of any strain or duration",
        "Crohn's disease confirmed by standard diagnostic criteria",
    ],
    exclusion=[
        "Animal or in vitro study",
        "Conference abstract without full-text availability",
        "Not published in English",
    ],
)

# articles is a list of objects satisfying the ScreenableArticle protocol:
# each must have .id (str), .title (str), and .abstract (str | None).
#
# Article objects from litprism-pubmed, litprism-europepmc, and
# litprism-semanticscholar satisfy this protocol directly.
#
# You can also use plain dataclasses or any object with matching attributes:
from dataclasses import dataclass

@dataclass
class SimpleArticle:
    id: str
    title: str
    abstract: str | None

articles = [
    SimpleArticle(
        id="pmid_31009449",
        title="Probiotic therapy in active Crohn's disease: a randomised controlled trial",
        abstract=(
            "Background: Probiotics have shown promise in IBD management. "
            "Methods: Adults (≥18) with confirmed Crohn's disease were randomised "
            "to probiotic or placebo for 12 weeks..."
        ),
    ),
    SimpleArticle(
        id="pmid_29256392",
        title="Gut microbiome in murine colitis models",
        abstract="We investigated probiotic effects in DSS-induced colitis in mice...",
    ),
]

# Screen a batch — returns one ScreeningResult per article
results = await screener.ascreen_batch(articles, criteria)

for result in results:
    print(f"{result.article_id}: {result.decision} (confidence {result.confidence:.2f})")
    for hit in result.criteria_hits:
        print(f"  [{hit.criterion_type}] {hit.criterion}: {hit.assessment.value}")
        if hit.supporting_quote:
            print(f"    → '{hit.supporting_quote}'")
        if hit.unassessable_reason:
            print(f"    → Cannot assess: {hit.unassessable_reason}")

# Example output:
# pmid_31009449: include (confidence 0.95)
#   [inclusion] Randomised controlled trial: confirmed
#     → 'were randomised to probiotic or placebo'
#   [inclusion] Adult participants (≥18 years): confirmed
#     → 'Adults (≥18)'
#   [exclusion] Animal or in vitro study: refuted
#     → 'Adults (≥18) with confirmed Crohn's disease'
#
# pmid_29256392: exclude (confidence 0.97)
#   [exclusion] Animal or in vitro study: confirmed
#     → 'DSS-induced colitis in mice'
```

### Input: the `ScreenableArticle` protocol

`ascreen_batch()` accepts any object satisfying:

```python
class ScreenableArticle(Protocol):
    @property
    def id(self) -> str: ...               # unique identifier

    @property
    def title(self) -> str: ...            # required

    @property
    def abstract(self) -> str | None: ... # None → always routed to uncertain
```

Articles with `abstract=None` are always routed to `uncertain` — the
screener cannot assess inclusion criteria without text.

---

## Screening methodology

### Basis in established systematic review practice

The decision logic in `litprism-screen` follows the eligibility
assessment framework codified in the Cochrane Handbook for Systematic
Reviews of Interventions [1] and implemented in standard tools such as
Covidence and Rayyan [2]. The core rules are:

**Rule 1 — Exclusion short-circuits.**
A study needs to meet only *one* exclusion criterion to be excluded.
As soon as a confirmed exclusion is found, screening stops — no further
criteria need to be evaluated [3].

**Rule 2 — Inclusion requires all criteria to be met.**
A study must satisfy *every* inclusion criterion to advance [3].

**Rule 3 — Insufficient information is not exclusion.**
When an abstract does not contain enough information to assess a criterion,
the article is marked `uncertain` and routed to full-text review — not
excluded [2, 4]. This mirrors the standard Covidence/Rayyan "Maybe" outcome.
Abstracting too little from a title/abstract is a recognised limitation
of this screening stage; the conservative approach is to retrieve the
full text rather than exclude prematurely [5].

### The three-state criterion assessment

A binary `include / exclude` per criterion is insufficient and leads to
false exclusions. There is a critical difference between:

- An abstract that **confirms** a criterion is met or triggered
- An abstract that **refutes** it — citing text that explicitly contradicts it
- An abstract that **does not mention** the criterion at all

LLM-based screeners are known to conflate the last two categories —
treating silence as negative evidence — which increases false exclusion
rates [5, 6]. `litprism-screen` addresses this by requiring the LLM to
assign one of three explicit assessments to each criterion:

| Assessment | Meaning | Quote required? |
|---|---|---|
| `confirmed` | Criterion clearly met (inclusion) or triggered (exclusion) | Yes — exact phrase from title/abstract |
| `refuted` | Text explicitly contradicts the criterion | Yes — exact phrase showing the contradiction |
| `unassessable` | Abstract lacks sufficient information | No — brief reason required instead |

**`refuted` requires a contradicting quote, not just absence.**
For example, to refute an inclusion criterion of "randomised controlled trial",
the model must cite a phrase such as `"retrospective cohort study"` that
explicitly establishes a different study design. An abstract that simply does
not describe study design is `unassessable`, not `refuted`. This distinction
is enforced at the prompt level and validated in grounding.

### Deterministic decision derivation

A common failure mode in LLM-based screening is delegating the final
`include / exclude / uncertain` decision to the model — which means the
decision varies with LLM temperature, phrasing, and prompt wording rather
than following a consistent rule [5, 7]. In `litprism-screen`, the LLM's
only job is to populate per-criterion assessments. The final decision is
derived by a pure, deterministic Python function (`derive_decision()`)
that applies the rules above in a fixed priority order:

```
Priority 1: Any exclusion confirmed?          → exclude   (immediate, no further checks)
Priority 2: Any inclusion unassessable?       → uncertain (the "Maybe" in Covidence/Rayyan — routes to full-text)
Priority 3: Any inclusion refuted?            → exclude
Priority 4: All inclusion confirmed, no
            exclusions triggered?             → include
```

This function has no LLM dependency and is comprehensively unit-tested.
The audit log shows exactly which rule fired for every decision.

### Grounding and quote validation

Every `confirmed` or `refuted` assessment must be grounded in an exact
quote from the title or abstract. The validator performs a case-insensitive
substring search to verify the quote exists in the source text. This applies
equally to `confirmed` and `refuted` — a claimed contradiction must be
traceable to actual text, not inferred or paraphrased.

If a quote cannot be verified in the source text:
- The assessment is retained (to avoid silently changing the LLM output)
- A warning is logged with the criterion and the unverified quote
- A `quote_verified: False` flag is recorded for human audit

Fuzzy matching is intentionally not used in v1 — the false positive rate
when LLMs paraphrase is too high to be useful for audit purposes.

---

## Full-text screening (Stage 2)

`litprism-screen` handles the *screening logic* for full-text articles
using the same `Screener` and `derive_decision()` machinery as Stage 1.
The only difference is the input: Stage 2 receives extracted full text
instead of an abstract.

**PDF extraction is not part of this package.** Full-text retrieval and
parsing is handled upstream:

- In `litprism-app`, `services/parsers/pdf.py` extracts text from PDFs
  using `pdfplumber`.
- For open-access articles, the pipeline retrieves full text directly from
  Europe PMC or PubMed Central APIs, bypassing PDF extraction entirely.
- You can supply full text from any source — the screener accepts a plain string.

```python
# Stage 2: pass extracted full text in the abstract field
full_text_articles = [
    SimpleArticle(
        id="pmid_31009449",
        title="Probiotic therapy in active Crohn's disease...",
        abstract=extracted_full_text_string,  # from your PDF parser or API
    ),
]

results = await screener.ascreen_batch(
    full_text_articles,
    criteria,
    stage="fulltext",  # recorded in ScreeningResult.stage for audit trail
)
```

This design keeps `litprism-screen` dependency-light and usable in any
pipeline, regardless of how full text is obtained.

---

## Configuration

### LLM providers

`litprism-screen` uses [litellm](https://github.com/BerriAI/litellm) for
provider abstraction. Supported: OpenAI, Azure OpenAI, Ollama (local),
and any litellm-compatible endpoint.

```bash
# OpenAI (recommended default)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-5.4-mini        # verified: passes all integration tests

# Azure OpenAI
LLM_PROVIDER=azure
AZURE_API_KEY=...
AZURE_API_BASE=https://your-endpoint.openai.azure.com/
AZURE_API_VERSION=2024-02-01
AZURE_DEPLOYMENT_NAME=gpt-4o

# Local (Ollama — no API cost, requires local GPU)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b          # recommended local option — see Tested models below
```

### Tested models

Models are listed as verified once they pass all three integration tests
(`test_live_include`, `test_live_exclude_on_exclusion`, `test_live_uncertain`).
Benchmarks are on Apple M4 24GB unified memory.

| Model | Provider | Integration tests | tok/s (M4 24GB) | Notes |
|---|---|---|---|---|
| `gpt-5.4-mini` | OpenAI | ✅ 3/3 | API | Recommended default. 400k context, strong JSON adherence |
| `qwen2.5:7b` | Ollama | ✅ 3/3 | 12.3 | Recommended local. Best reliability/speed on M4 |
| `qwen2.5:14b` | Ollama | ✅ 3/3 | 21.9 | Good local quality. Requires `_extract_json` fallback for occasional preamble |
| `llama3.3:70b` | Ollama | ⏳ not yet run | — | Best local quality — 48GB RAM required |
| `llama3.2` | Ollama | ❌ 0/3 | — | Not supported — too small for three-state assessment |

Models below ~7B parameters generally lack the instruction-following reliability
needed for three-state criterion assessment. `llama3.2` (3B) is explicitly
not supported.

If you test a model not listed here, open a PR updating this table.

### Estimated cost (OpenAI)

The following estimates apply to abstract screening with `gpt-5.4-mini`
($0.75/1M input tokens, $4.50/1M output tokens), assuming an average
abstract of ~250 words and 4 criteria (2 inclusion, 2 exclusion).
Actual costs vary with abstract length and number of criteria.

| Articles screened | Estimated cost |
|---|---|
| 100 | ~$0.15 |
| 500 | ~$0.75 |
| 1,000 | ~$1.50 |
| 5,000 | ~$7.50 |
| 10,000 | ~$15.00 |

`gpt-5.4-mini` is recommended for abstract screening: strong reasoning
and JSON reliability at significantly lower cost than the flagship model.
Sensitivity — not missing relevant studies — is the critical metric at
this stage, and smaller models in the GPT-5 family retain the instruction-
following quality needed for the three-state assessment.

For Stage 2 (full-text), costs are 5–15× higher per article due to
longer inputs. Most reviews send 50–200 articles to full-text screening,
so total cost remains modest.

### Conservatism by review type

The conservatism instruction in the prompt controls how the LLM handles
genuinely ambiguous *in-text* evidence — that is, text that could be
read either way. It does not affect absent information, which is always
`unassessable` regardless of review type.

| Review type | Conservatism | Prompt effect |
|---|---|---|
| `systematic` | High | Prefer `unassessable` over `refuted` for borderline in-text cases |
| `rapid` | High | Same as systematic |
| `scoping` | Medium | Moderate judgement on borderline in-text evidence |
| `literature` | Low | May mark clearly irrelevant articles as `refuted` |
| `state_of_art` | Low | Same as literature |

This exposes Review Type as the configuration knob — a concept that has
clear meaning to researchers — rather than temperature or top-p, which do not.

### Concurrency, timeouts, and retries

Default concurrency is 10 simultaneous LLM requests. Adjust based on
your API tier:

```python
screener = Screener.from_env(concurrency=5)   # conservative, fewer rate-limit hits
screener = Screener.from_env(concurrency=25)  # higher throughput on paid tiers
```

`litprism-screen` uses `asyncio.Semaphore` internally. This is preferable
to raw `asyncio.gather` because a rate-limit error mid-batch with gather
causes all in-flight requests to fail simultaneously. With a semaphore,
excess requests queue rather than fail.

**Timeouts:** each LLM call has a default timeout of 60 seconds.
LLM providers occasionally hang — especially under load — and an
unhandled hang would stall the entire batch. If a call times out,
it is retried before being marked as failed.

**Retries:** `litprism-screen` uses `tenacity` to retry on 429
(rate limited) and 503 (service unavailable) responses, with
exponential back-off (initial wait 1 s, max 60 s, max 3 attempts).
Persistent failures after retries surface as a `ScreeningError`
with the article ID, so the rest of the batch continues unaffected.

---

## Output format

Each `ScreeningResult` contains:

```python
class ScreeningResult(BaseModel):
    article_id: str
    decision: Literal["include", "exclude", "uncertain"]
    confidence: float                      # 0.0–1.0, reported by LLM
    reasoning: str                         # 2–3 sentence plain-English explanation
    criteria_hits: list[CriteriaHit]       # one entry per criterion
    stage: Literal["abstract", "fulltext"]
    model_used: str                        # e.g. "gpt-4o-mini"
    llm_provider: str                      # e.g. "openai"
    screened_at: datetime

    # Populated during human review
    human_override: bool = False
    human_decision: str | None = None
    human_note: str | None = None
```

Each `CriteriaHit`:

```python
class CriteriaHit(BaseModel):
    criterion: str
    criterion_type: Literal["inclusion", "exclusion"]
    assessment: CriteriaAssessment         # confirmed | refuted | unassessable
    supporting_quote: str | None           # exact text from source
    quote_location: Literal["title", "abstract", "section"] | None
    unassessable_reason: str | None        # populated when assessment is unassessable
```

---

## Human-in-the-loop

`litprism-screen` is designed to assist human reviewers, not replace them.
Research shows LLMs achieve high sensitivity but variable specificity in
abstract screening tasks [7, 8], and current guidance recommends
human-in-the-loop designs to catch erroneous exclusions [5].

Recommended workflow:

1. Run LLM screening on all abstracts.
2. Auto-apply confident `include` and `exclude` decisions (confidence > 0.90).
3. Route all `uncertain` articles to human full-text review.
4. Route low-confidence decisions (confidence ≤ 0.90) to human spot-check.
5. For rigorous reviews, have a second reviewer validate a random sample
   of LLM `exclude` decisions to verify the exclusion rate is plausible.

Human overrides are recorded in `human_override`, `human_decision`, and
`human_note` for full provenance in the PRISMA audit trail.

---

## Development

```bash
git clone git@github.com:bmtime/litprism.git
cd litprism
uv sync --package litprism-screen

# Unit tests — no API key needed, LLM is fully mocked
uv run pytest packages/litprism-screen/tests/ -v

# Integration tests — requires LLM API key in .env
uv run pytest packages/litprism-screen/tests/integration/ -v -m integration

# Lint and format
uv run ruff check packages/litprism-screen/
uv run ruff format packages/litprism-screen/
```

---

## References

[1] Higgins JPT, Thomas J, Chandler J, et al. *Cochrane Handbook for
Systematic Reviews of Interventions*, version 6.4. Cochrane, 2023.
https://training.cochrane.org/handbook

[2] Ouzzani M, Hammady H, Fedorowicz Z, Elmagarmid A. Rayyan — a web
and mobile app for systematic reviews. *Systematic Reviews* 5, 210 (2016).
https://doi.org/10.1186/s13643-016-0384-4

[3] Rosalind Franklin University Libraries. Inclusion and Exclusion
Criteria — Searching Best Practices for Evidence Synthesis Reviews.
https://guides.rosalindfranklin.edu/systematic-searching/inclusion-exclusion

[4] Hackensack Meridian School of Medicine Library. Study Selection or
Screening — Systematic Reviews.
https://library.hmsom.edu/SystematicReviews/Screening

[5] Dennstadt F, Roth JA, Naber CK, et al. Development and evaluation of
prompts for a large language model to screen titles and abstracts in a
living systematic review. *BMJ Open* (2025).
https://pmc.ncbi.nlm.nih.gov/articles/PMC12306261/

[6] Syriani E, David I, Kumar G. Large Language Models in Systematic
Review Screening: Opportunities, Challenges, and Methodological
Considerations. *Information* 16(5), 378 (2025).
https://doi.org/10.3390/info16050378

[7] Guo E, Gupta M, Deng J, et al. High-performance automated abstract
screening with large language model ensembles. *JAMIA Open* (2024).
https://pmc.ncbi.nlm.nih.gov/articles/PMC12012331/

[8] Huang S, Zhuang Y, et al. Evaluating the effectiveness of large
language models in abstract screening: a comparative analysis.
*Systematic Reviews* 13, 210 (2024).
https://doi.org/10.1186/s13643-024-02609-x

---

## Licence

MIT — see [LICENSE](../../LICENSE)