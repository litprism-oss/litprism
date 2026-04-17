import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Lock } from 'lucide-react'
import {
  useSearchRuns,
  useCreateSearchRun,
  useUpdateSearchRun,
  useExecuteSearch,
  useSearchPreview,
} from '@/hooks/useSearchRuns'
import { useSearchProgress } from '@/hooks/useSearchProgress'
import { PICOForm } from '@/components/search/PICOForm'
import { QueryPreview } from '@/components/search/QueryPreview'
import { FilterPanel, type SearchFilters } from '@/components/search/FilterPanel'
import { SourceSelector } from '@/components/search/SourceSelector'
import { SearchScopePreview } from '@/components/search/SearchScopePreview'
import { SearchProgress } from '@/components/search/SearchProgress'
import type { SearchPreviewResponse } from '@/lib/types'

type Mode = 'pico' | 'freetext'
type Source = 'pubmed' | 'europepmc' | 'semanticscholar'
type PageState = 'building' | 'previewing' | 'previewed' | 'running' | 'complete'

interface PICOValues {
  population: string
  intervention: string
  comparator: string
  outcome: string
}

function buildQueryNatural(mode: Mode, pico: PICOValues, freeText: string): string {
  if (mode === 'freetext') return freeText
  return [pico.population, pico.intervention, pico.comparator, pico.outcome]
    .filter(Boolean)
    .join(' ')
}

export function SearchPage() {
  const { projectId = '' } = useParams()

  const [mode, setMode] = useState<Mode>('pico')
  const [picoValues, setPicoValues] = useState<PICOValues>({
    population: '',
    intervention: '',
    comparator: '',
    outcome: '',
  })
  const [freeText, setFreeText] = useState('')
  const [filters, setFilters] = useState<SearchFilters>({})
  const [selectedSources, setSelectedSources] = useState<Source[]>([
    'pubmed',
    'europepmc',
    'semanticscholar',
  ])
  const [pageState, setPageState] = useState<PageState>('building')
  const [draftRunId, setDraftRunId] = useState<string | null>(null)
  const [lastPreviewedAt, setLastPreviewedAt] = useState<Date | null>(null)
  const [previewData, setPreviewData] = useState<SearchPreviewResponse | null>(null)
  const [previewError, setPreviewError] = useState<Error | null>(null)
  const [startedAt, setStartedAt] = useState<Date | null>(null)

  const hasInitialized = useRef(false)
  const lastSavedQuery = useRef<string | null>(null)

  const { data: searchRunsData } = useSearchRuns(projectId)
  const createRun = useCreateSearchRun(projectId)
  const updateRun = useUpdateSearchRun(projectId, draftRunId ?? '')
  const executeSearch = useExecuteSearch(projectId, draftRunId ?? '')
  const previewMutation = useSearchPreview(projectId)
  const { events, clearEvents } = useSearchProgress(projectId)

  // Find or create draft run on load
  useEffect(() => {
    if (!searchRunsData || hasInitialized.current) return
    hasInitialized.current = true

    const draft = searchRunsData.find((r) => r.status === 'draft')
    if (draft) {
      setDraftRunId(draft.id)
      if (draft.query_natural) {
        setMode('freetext')
        setFreeText(draft.query_natural)
        lastSavedQuery.current = draft.query_natural
      }
      if (draft.filters) {
        setFilters(draft.filters as SearchFilters)
      }
    } else {
      createRun.mutateAsync({}).then((newRun) => {
        setDraftRunId(newRun.id)
        lastSavedQuery.current = ''
      }).catch(() => {})
    }
  }, [searchRunsData]) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced save on query/filter changes
  useEffect(() => {
    if (!draftRunId || pageState === 'running' || pageState === 'complete') return
    const currentQuery = buildQueryNatural(mode, picoValues, freeText)
    if (currentQuery === lastSavedQuery.current) return

    const timer = setTimeout(() => {
      lastSavedQuery.current = currentQuery
      updateRun.mutate({ query_natural: currentQuery, filters: filters as Record<string, unknown> })
    }, 500)
    return () => clearTimeout(timer)
  }, [picoValues, freeText, mode, filters, draftRunId]) // eslint-disable-line react-hooks/exhaustive-deps

  const currentQuery = buildQueryNatural(mode, picoValues, freeText)

  // Derive the displayed PubMed query
  const draftRun = searchRunsData?.find((r) => r.id === draftRunId)
  const canonicalQuery = draftRun?.query_generated ?? draftRun?.query_final ?? (mode === 'freetext' ? currentQuery : '')

  const handlePreview = () => {
    if (!canonicalQuery.trim()) return
    setPageState('previewing')
    setPreviewError(null)
    previewMutation.mutate(
      { query_final: canonicalQuery, filters: filters as Record<string, unknown> },
      {
        onSuccess: (data) => {
          setPreviewData(data)
          setLastPreviewedAt(new Date())
          setPageState('previewed')
        },
        onError: (err) => {
          setPreviewError(err instanceof Error ? err : new Error('Preview failed'))
          setPageState('previewed')
        },
      },
    )
  }

  const handleExecute = useCallback(() => {
    if (!draftRunId) return
    clearEvents()
    executeSearch.mutate(undefined, {
      onSuccess: () => {
        setStartedAt(new Date())
        setPageState('running')
      },
      onError: () => {},
    })
  }, [draftRunId, clearEvents, executeSearch])

  const queryFinal = draftRun?.query_final ?? null
  const hasFieldTags = /\[(tiab|MeSH|ti|ab|pt|la|au)\]/i.test(queryFinal ?? '')
  const hasRefinedQuery = !!queryFinal && hasFieldTags

  const canPreview = !!currentQuery.trim() && pageState !== 'running' && pageState !== 'complete'
  const canExecute = !!draftRunId && !!currentQuery.trim() && pageState !== 'running' && pageState !== 'complete'

  if (pageState === 'running' || pageState === 'complete') {
    return (
      <div style={{ padding: '24px', maxWidth: '680px' }}>
        <SearchProgress
          events={events}
          startedAt={startedAt ?? new Date()}
          projectId={projectId}
          onComplete={() => setPageState('complete')}
        />
      </div>
    )
  }

  return (
    <div style={{ padding: '24px', maxWidth: '680px' }}>
      {/* Mode toggle */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 'var(--border-radius-md)',
          width: 'fit-content',
          overflow: 'hidden',
          marginBottom: '20px',
        }}
      >
        {(['pico', 'freetext'] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              padding: '6px 14px',
              fontSize: '13px',
              cursor: 'pointer',
              border: 'none',
              background: mode === m ? 'var(--color-background-secondary)' : 'transparent',
              color: mode === m ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              fontWeight: mode === m ? 500 : 400,
            }}
          >
            {m === 'pico' ? 'PICO' : 'Free text'}
          </button>
        ))}
      </div>

      {/* Query input */}
      {mode === 'pico' ? (
        <PICOForm values={picoValues} onChange={setPicoValues} />
      ) : (
        <textarea
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          placeholder='e.g. ("Crohn disease"[MeSH]) AND probiotic*[tiab]'
          style={{
            width: '100%',
            fontSize: '13px',
            fontFamily: 'var(--font-mono)',
            resize: 'vertical',
            minHeight: '80px',
            marginBottom: '16px',
            boxSizing: 'border-box',
          }}
        />
      )}

      <QueryPreview canonicalQuery={canonicalQuery} mode={mode} />

      <FilterPanel filters={filters} onChange={setFilters} />
      <SourceSelector selected={selectedSources} onChange={setSelectedSources} />

      <SearchScopePreview
        data={previewData ?? undefined}
        isLoading={pageState === 'previewing'}
        error={previewError}
        lastPreviewedAt={lastPreviewedAt}
        onPreviewAgain={handlePreview}
      />

      {/* Action row */}
      <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
        <button
          onClick={handlePreview}
          disabled={!canPreview}
          style={{
            padding: '8px 16px',
            fontSize: '13px',
            border: '0.5px solid var(--color-border-secondary)',
            borderRadius: 'var(--border-radius-md)',
            background: 'transparent',
            color: 'var(--color-text-primary)',
            cursor: canPreview ? 'pointer' : 'not-allowed',
            opacity: canPreview ? 1 : 0.5,
          }}
        >
          {pageState === 'previewing' ? 'Previewing…' : hasRefinedQuery ? 'Preview scope' : 'Preview rough scope'}
        </button>
        <button
          onClick={handleExecute}
          disabled={!canExecute}
          style={{
            padding: '8px 16px',
            fontSize: '13px',
            border: 'none',
            borderRadius: 'var(--border-radius-md)',
            background: 'var(--color-text-primary)',
            color: 'var(--color-background-primary)',
            cursor: canExecute ? 'pointer' : 'not-allowed',
            opacity: canExecute ? 1 : 0.5,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <Lock size={12} />
          {executeSearch.isPending ? 'Starting…' : 'Run full search'}
        </button>
      </div>
      {!hasRefinedQuery && (
        <p style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 4 }}>
          Based on your search terms — refine the query for a more accurate estimate
        </p>
      )}
    </div>
  )
}
