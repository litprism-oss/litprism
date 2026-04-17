import { useEffect, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import type { SearchProgressEvent } from '@/hooks/useSearchProgress'
import { formatCount } from '@/lib/utils'

const SOURCES = ['pubmed', 'europepmc', 'semanticscholar'] as const
const SOURCE_LABELS: Record<string, string> = {
  pubmed: 'PubMed',
  europepmc: 'Europe PMC',
  semanticscholar: 'Semantic Scholar',
}

interface SearchProgressProps {
  events: SearchProgressEvent[]
  startedAt: Date
  projectId: string
  onComplete: () => void
}

export function SearchProgress({ events, startedAt, projectId, onComplete }: SearchProgressProps) {
  const qc = useQueryClient()
  const navigate = useNavigate()

  const isComplete = events.some((e) => e.event === 'search_complete')
  const completeEvent = events.find((e) => e.event === 'search_complete')

  const sourceState = useMemo(() => {
    const map: Record<string, { fetched: number; total: number }> = {}
    for (const ev of events) {
      if (ev.event === 'search_progress' && ev.source) {
        map[ev.source] = { fetched: ev.fetched ?? 0, total: ev.total ?? 0 }
      }
    }
    return map
  }, [events])

  useEffect(() => {
    if (isComplete) {
      qc.invalidateQueries({ queryKey: ['searchRuns', projectId] })
      onComplete()
    }
  }, [isComplete]) // eslint-disable-line react-hooks/exhaustive-deps

  const startTimeStr =
    startedAt.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
    }) + ' UTC'

  const totalFetched = Object.values(sourceState).reduce((sum, s) => sum + s.fetched, 0)

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: '20px',
          fontSize: '13px',
        }}
      >
        <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>
          {isComplete ? 'Search complete' : 'Search in progress'}
        </span>
        <span style={{ color: 'var(--color-text-secondary)' }}>Started {startTimeStr}</span>
      </div>

      {SOURCES.map((source) => {
        const state = sourceState[source]
        const done = !!state && state.total > 0 && state.fetched >= state.total
        const pct = state && state.total > 0 ? Math.min(100, (state.fetched / state.total) * 100) : 0

        return (
          <div key={source} style={{ marginBottom: '16px' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: '6px',
                fontSize: '13px',
              }}
            >
              <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>
                {SOURCE_LABELS[source]}
              </span>
              {done ? (
                <span
                  style={{
                    fontSize: '12px',
                    background: '#EAF3DE',
                    color: '#27500A',
                    padding: '2px 8px',
                    borderRadius: '99px',
                  }}
                >
                  ✓ {formatCount(state.fetched)}
                </span>
              ) : state ? (
                <span style={{ color: 'var(--color-text-secondary)' }}>
                  {formatCount(state.fetched)} / {formatCount(state.total)}
                </span>
              ) : (
                <span style={{ color: 'var(--color-text-tertiary)' }}>Waiting…</span>
              )}
            </div>
            <div
              style={{
                height: '6px',
                background: 'var(--color-background-secondary)',
                borderRadius: '99px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  borderRadius: '99px',
                  background: done ? '#639922' : 'var(--color-text-primary)',
                  width: `${pct}%`,
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
          </div>
        )
      })}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          paddingTop: '16px',
          borderTop: '0.5px solid var(--color-border-tertiary)',
          fontSize: '13px',
        }}
      >
        <span style={{ color: 'var(--color-text-secondary)' }}>
          {isComplete ? 'Total collected' : 'Total so far'}
        </span>
        <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>
          {completeEvent?.total_articles != null
            ? formatCount(completeEvent.total_articles)
            : formatCount(totalFetched)}{' '}
          articles
        </span>
      </div>

      {isComplete && (
        <div style={{ marginTop: '16px' }}>
          <button
            onClick={() => navigate(`/projects/${projectId}`)}
            style={{
              fontSize: '13px',
              padding: '8px 16px',
              border: '0.5px solid var(--color-border-secondary)',
              borderRadius: 'var(--border-radius-md)',
              background: 'transparent',
              color: 'var(--color-text-primary)',
              cursor: 'pointer',
            }}
          >
            View articles
          </button>
        </div>
      )}
    </div>
  )
}
