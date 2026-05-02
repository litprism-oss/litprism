import { useState } from 'react'
import { useScreeningResults } from '@/hooks/useScreeningResults'
import { DecisionBadge } from './DecisionBadge'
import { ScreeningDetailPanel } from './ScreeningDetailPanel'
import type { ArticleWithResult, ScreeningDecision } from '@/lib/types'

const SOURCE_COLOURS: Record<string, { bg: string; text: string }> = {
  pubmed:          { bg: '#E6F1FB', text: '#0C447C' },
  europepmc:       { bg: '#E1F5EE', text: '#085041' },
  semanticscholar: { bg: '#EEEDFE', text: '#3C3489' },
  upload:          { bg: '#F1EFE8', text: '#444441' },
}

const SOURCE_LABELS: Record<string, string> = {
  pubmed:          'PubMed',
  europepmc:       'Europe PMC',
  semanticscholar: 'Semantic Scholar',
  upload:          'Upload',
}

type FilterTab = 'all' | ScreeningDecision

const TABS: { key: FilterTab; label: string }[] = [
  { key: 'all',       label: 'All' },
  { key: 'include',   label: 'Include' },
  { key: 'exclude',   label: 'Exclude' },
  { key: 'uncertain', label: 'Uncertain' },
  { key: 'error',     label: 'Failed' },
]

const PAGE_SIZE = 50

interface ResultsTableProps {
  projectId: string
  runId?: string
  activeTab?: FilterTab
  onTabChange?: (tab: FilterTab) => void
}

export function ResultsTable({ projectId, runId, activeTab: controlledTab, onTabChange }: ResultsTableProps) {
  const [internalTab, setInternalTab]   = useState<FilterTab>('all')
  const activeTab = controlledTab ?? internalTab
  const [page, setPage]                 = useState(1)
  const [selected, setSelected]         = useState<ArticleWithResult | null>(null)

  const params = {
    run_id:    runId,
    decision:  activeTab === 'all' ? undefined : activeTab,
    page,
    page_size: PAGE_SIZE,
  }

  const { data, isLoading, isError } = useScreeningResults(projectId, params)

  function handleTabChange(tab: FilterTab) {
    setInternalTab(tab)
    onTabChange?.(tab)
    setPage(1)
  }

  function confidenceColour(conf: number): string {
    if (conf >= 0.9) return 'var(--color-text-secondary)'
    if (conf >= 0.75) return '#633806'
    return '#791F1F'
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1

  return (
    <>
      {/* Filter tabs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => handleTabChange(t.key)}
            style={{
              fontSize: 12,
              padding: '4px 10px',
              borderRadius: 99,
              border: '0.5px solid var(--color-border-tertiary)',
              cursor: 'pointer',
              background: activeTab === t.key ? 'var(--color-text-primary)' : 'none',
              color: activeTab === t.key ? 'var(--color-background-primary)' : 'var(--color-text-secondary)',
              borderColor: activeTab === t.key ? 'var(--color-text-primary)' : 'var(--color-border-tertiary)',
            }}
          >
            {t.label}
          </button>
        ))}
        {data && (
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--color-text-secondary)' }}>
            {data.total.toLocaleString()} total
          </span>
        )}
      </div>

      {/* Table */}
      {isLoading && (
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', padding: '16px 0' }}>Loading…</p>
      )}
      {isError && (
        <p style={{ fontSize: 13, color: '#791F1F', padding: '16px 0' }}>Failed to load results.</p>
      )}
      {data && data.items.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', padding: '16px 0' }}>No articles found.</p>
      )}
      {data && data.items.map(article => {
        const result = article.screening_result
        const srcColour = SOURCE_COLOURS[article.source] ?? SOURCE_COLOURS.upload
        const srcLabel  = SOURCE_LABELS[article.source]  ?? article.source

        return (
          <div
            key={article.id}
            onClick={() => setSelected(article)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 0',
              borderBottom: '0.5px solid var(--color-border-tertiary)',
              cursor: 'pointer',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-background-secondary)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span style={{ flex: 1, fontSize: 13, color: 'var(--color-text-primary)', lineHeight: 1.4 }}>
              {article.title}
            </span>
            {result ? (
              <>
                <DecisionBadge decision={result.decision} human_override={result.human_override} size="sm" />
                <span
                  style={{
                    fontSize: 12,
                    width: 36,
                    textAlign: 'right',
                    flexShrink: 0,
                    color: confidenceColour(result.confidence),
                    fontWeight: result.confidence < 0.75 ? 500 : undefined,
                  }}
                >
                  {Math.round(result.confidence * 100)}%
                </span>
              </>
            ) : (
              <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>—</span>
            )}
            <span
              style={{
                fontSize: 11,
                padding: '1px 7px',
                borderRadius: 99,
                background: srcColour.bg,
                color: srcColour.text,
                flexShrink: 0,
              }}
            >
              {srcLabel}
            </span>
          </div>
        )
      })}

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center' }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ fontSize: 12, padding: '4px 10px', borderRadius: 6, border: '0.5px solid var(--color-border-tertiary)', cursor: page === 1 ? 'default' : 'pointer', opacity: page === 1 ? 0.4 : 1 }}
          >
            ← Prev
          </button>
          <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{ fontSize: 12, padding: '4px 10px', borderRadius: 6, border: '0.5px solid var(--color-border-tertiary)', cursor: page === totalPages ? 'default' : 'pointer', opacity: page === totalPages ? 0.4 : 1 }}
          >
            Next →
          </button>
        </div>
      )}

      {/* Detail panel */}
      <ScreeningDetailPanel
        projectId={projectId}
        article={selected}
        onClose={() => setSelected(null)}
      />
    </>
  )
}
