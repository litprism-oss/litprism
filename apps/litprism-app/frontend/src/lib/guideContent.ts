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
        body: 'Set inclusion and exclusion criteria before screening begins. Changes after screening create a new criteria version — all articles are re-screened and both versions are preserved.',
      },
      {
        heading: 'PRISMA-S item 5',
        body: 'Criteria are versioned with timestamps. If you update them, the change history appears in your screening report with the date and nature of the change.',
      },
    ],
  },
  screening: {
    title: 'Abstract screening',
    sections: [
      {
        heading: 'LLM-assisted decisions',
        body: 'Each abstract is assessed against every criterion. Every decision is grounded in an exact quote. The LLM cannot exclude an article for a criterion that is simply not mentioned — absence of information routes the article to full-text review.',
      },
      {
        heading: 'Human review',
        body: 'Low-confidence decisions (below your threshold) are flagged for human review. Overrides are recorded in the audit trail.',
      },
    ],
  },
  export: {
    title: 'Reporting & export',
    sections: [
      {
        heading: 'PRISMA-S supplementary table',
        body: 'Automatically generated from your search history. Includes query strings, filters, dates, and result counts for every database searched and every file uploaded.',
      },
      {
        heading: 'Screening report',
        body: 'Includes exclusion reasons by criterion, confidence distribution, and criteria version history — all required for methods section reporting.',
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
