export interface GuideEntry {
  title: string
  sections: Array<{ heading: string; body: string }>
  links?: Array<{ label: string; url: string }>
}

export const GUIDE_CONTENT: Record<string, GuideEntry> = {
  overview: {
    title: 'Overview',
    sections: [
      {
        heading: 'Systematic review workflow',
        body: 'LitPrism follows the PRISMA 2020 standard. Each step — Search, Screen, Export — maps to required reporting sections. Complete them in order for a fully auditable review.',
      },
    ],
    links: [{ label: 'PRISMA 2020 checklist', url: 'https://prisma-statement.org' }],
  },
  articles: {
    title: 'Article pool',
    sections: [
      {
        heading: 'Verify your results',
        body: 'Review retrieved articles before screening. Check that titles and abstracts look relevant — if the pool looks wrong, refine your query and re-run the search.',
      },
      {
        heading: 'Data quality (uploads)',
        body: 'The quality summary shows how many records have titles, abstracts, authors, and DOIs. Missing abstracts mean those articles cannot be LLM-screened and will go directly to full-text review.',
      },
      {
        heading: 'Next step',
        body: 'Once you are satisfied with the article pool, set up your eligibility criteria before running screening.',
      },
    ],
  },
  search: {
    title: 'Database searching',
    sections: [
      {
        heading: 'PRISMA-S items 1 & 2',
        body: 'Record the exact query string and filters used in each database. LitPrism stores these automatically when you run a search.',
      },
      {
        heading: 'Query locking',
        body: 'For systematic, scoping, and rapid reviews, the query is locked permanently when the search runs. This ensures reproducibility and satisfies journal submission requirements.',
      },
      {
        heading: 'API vs upload',
        body: 'API search covers PubMed, Europe PMC, and Semantic Scholar up to ~10,000 results each. For Scopus, WoS, Embase, or larger result sets, export from the database website and upload the file.',
      },
    ],
  },
  upload: {
    title: 'Supplementary searching',
    sections: [
      {
        heading: 'PRISMA-S item 6',
        body: 'Manual searches, grey literature, and database exports count as supplementary sources. The source database and search strategy you record here appear in your PRISMA-S supplementary table.',
      },
      {
        heading: 'Deduplication',
        body: 'Uploaded articles are automatically deduplicated against existing articles using DOI, PMID, and fuzzy title matching. The deduplication log is preserved for audit.',
      },
    ],
  },
  criteria: {
    title: 'Eligibility criteria',
    sections: [
      {
        heading: 'Define before screening',
        body: 'Set your inclusion and exclusion criteria before running screening. Every criterion you add will be assessed by the LLM for each abstract.',
      },
      {
        heading: 'Versioning',
        body: 'Each save creates a new version. If you update criteria after screening has started, articles already screened are flagged as stale and can be re-screened under the new version.',
      },
      {
        heading: 'Writing good criteria',
        body: 'Be specific and assessable from an abstract. "Randomised controlled trial" is assessable. "High-quality study" is not — the LLM cannot judge quality from a title and abstract alone.',
      },
    ],
  },
  screening: {
    title: 'Abstract screening',
    sections: [
      {
        heading: 'How it works',
        body: 'Each abstract is assessed against every criterion. The LLM must cite an exact quote to confirm or refute a criterion — silence is never treated as negative evidence.',
      },
      {
        heading: 'Decisions',
        body: 'Include: all inclusion criteria confirmed, no exclusions triggered. Exclude: any exclusion confirmed, or any inclusion clearly refuted. Uncertain: insufficient information — routes to full-text review.',
      },
      {
        heading: 'Uncertain articles',
        body: 'Articles marked uncertain are not excluded — they proceed to full-text review. This is the correct trade-off for a systematic review: better to retrieve one extra article than to miss a relevant one.',
      },
    ],
  },
  'screening/results': {
    title: 'Screening results',
    sections: [
      {
        heading: 'Reviewing decisions',
        body: 'Click any article to see the full per-criterion assessment with supporting quotes. Override decisions where you disagree — overrides are recorded in the audit trail.',
      },
      {
        heading: 'Uncertain articles',
        body: 'Uncertain articles had insufficient information in the abstract to assess one or more criteria. These need full-text review before a final decision.',
      },
      {
        heading: 'Confidence score',
        body: 'Confidence reflects how clearly the abstract addressed all criteria. Low confidence (<75%) warrants human spot-check even when the decision looks correct.',
      },
    ],
  },
  export: {
    title: 'Export',
    sections: [
      {
        heading: 'Reference formats',
        body: 'RIS and NBIB can be imported directly into Zotero, EndNote, or any reference manager. CSV and JSON are for custom pipelines.',
      },
      {
        heading: 'PRISMA-S table',
        body: 'The supplementary search strategy document includes query strings, filters, dates, and result counts for every database searched — required by most journals for systematic review submission.',
      },
    ],
  },
  fulltext: {
    title: 'Full-text retrieval',
    sections: [
      {
        heading: 'Why retrieve full text?',
        body: 'Uncertain articles could not be assessed from their abstract alone. Full-text review is standard practice in systematic reviews — it gives the LLM (and human reviewers) complete information to make a final eligibility decision.',
      },
      {
        heading: 'What gets retrieved',
        body: 'LitPrism checks PMC Open Access for articles with a PMID, then Unpaywall for open-access PDFs. Around 50–70% of recent biomedical articles have an open-access version available.',
      },
      {
        heading: 'Unavailable articles',
        body: 'Articles marked "unavailable" are behind a paywall with no open-access version. These need manual retrieval — download the PDF from your institution and upload it, or review the full text manually and record your decision.',
      },
    ],
  },
  prisma: {
    title: 'PRISMA 2020 flow diagram',
    sections: [
      {
        heading: 'Live updates',
        body: 'This diagram is populated automatically from your search runs, uploads, deduplication log, and screening results. It updates every 30 seconds.',
      },
      {
        heading: 'Eligibility row',
        body: 'The Eligibility phase will populate when full-text screening is available (Session 10). Until then, uncertain abstracts are shown as the current included estimate.',
      },
      {
        heading: 'For submission',
        body: 'Download as SVG to embed in your manuscript, or use "Include in PRISMA-S .docx" to add it to your search strategy supplementary file.',
      },
    ],
    links: [{ label: 'PRISMA 2020 statement', url: 'https://prisma-statement.org' }],
  },
}
